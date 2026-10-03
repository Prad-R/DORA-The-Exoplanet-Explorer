"""Run one arm over a task list through Omnigent, one headless session per task.

    python runner/batch.py --arm v0_plain --tasks experiments/tasks.txt --out runs/v0 --workers 3

Each task gets runs/<out>/<task>/ with the materialized agent, tool-server state,
exported transcript and result.json. Finished tasks are skipped on rerun.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OMNIGENT_RUNTIME = REPO / ".omnigent-runtime"
sys.path.insert(0, str(REPO))

from lab.episode import FORBIDDEN  # noqa: E402
from runner.materialize import materialize  # noqa: E402

SESSION_RE = re.compile(r"/c/([0-9a-f]{32})")
GRACE_S = 180  # startup and shutdown allowance on top of the task's time budget


def _jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def run_task(arm: str, task_id: str, out: Path, max_observations: int = 3,
             max_compute_rounds: int = 4, research_prompt: str = "",
             live_logs: bool = False) -> dict:
    omnigent = shutil.which("omnigent")
    if not omnigent:
        raise RuntimeError(
            "Omnigent CLI was not found on PATH. Install/configure Omnigent, then reopen the shell "
            "and verify with `omnigent --version`."
        )
    run_dir = out / task_id
    result_path = run_dir / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    # Several batch processes may share an output directory; one task, one owner.
    lock = out / f".{task_id}.lock"
    if lock.exists():
        try:
            if _pid_running(int(lock.read_text().strip())):
                return None
        except ValueError:
            pass
    lock.write_text(str(os.getpid()))
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    agent_dir, brief = materialize(arm, task_id, run_dir,
                                   max_observations=max_observations,
                                   max_compute_rounds=max_compute_rounds,
                                   research_prompt=research_prompt)
    (run_dir / "brief.md").write_text(brief)
    budget = json.loads((run_dir / "budget.json").read_text())

    started = time.time()
    timed_out = False
    # Windows installations may deny writes to ~/.omnigent. Keep transient
    # Omnigent state and its own diagnostics inside this writable checkout.
    OMNIGENT_RUNTIME.mkdir(parents=True, exist_ok=True)
    omnigent_env = {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "OMNIGENT_DATA_DIR": str(OMNIGENT_RUNTIME),
        "OMNIGENT_CONFIG_HOME": str(OMNIGENT_RUNTIME),
        "OMNIGENT_LOG_TO_STDERR": "1" if live_logs else "0",
        # Omnigent's host protocol emits Unicode status markers. Force UTF-8
        # for its Windows child processes instead of the legacy cp1252 codec.
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    with open(run_dir / "omnigent.out", "w") as fo, open(run_dir / "omnigent.err", "w") as fe:
        popen_output = subprocess.PIPE if live_logs else fo
        proc = subprocess.Popen(
            [omnigent, "run", str(agent_dir), "-p", brief],
            stdin=subprocess.DEVNULL, stdout=popen_output,
            stderr=subprocess.STDOUT if live_logs else fe, text=live_logs, cwd=run_dir,
            # lab.policies is imported by the Omnigent runner.
            env=omnigent_env,
        )
        tee = None
        if live_logs:
            def copy_output() -> None:
                assert proc.stdout is not None
                for line in proc.stdout:
                    fo.write(line)
                    fo.flush()
                    print(f"[{task_id}] {line}", end="", flush=True)
            tee = Thread(target=copy_output, daemon=True)
            tee.start()
        try:
            proc.wait(timeout=budget["max_time"] + GRACE_S)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        if tee:
            tee.join(timeout=5)
    duration = time.time() - started

    session = SESSION_RE.search((run_dir / "omnigent.err").read_text())
    by_model: dict = {}
    cost, model, tool_calls, leak_hits, children = 0.0, None, {}, [], []

    def export(session_id: str, name: str) -> None:
        """Export one session (the top agent or a sub-agent) and fold in its usage and calls."""
        nonlocal cost, model
        path = run_dir / f"{name}.jsonl"
        subprocess.run([omnigent, "session", "export", "--id", session_id, "--output", str(path)],
                       capture_output=True)
        seen = set()
        for rec in _jsonl(path):
            if rec.get("record_type") == "session_meta":
                model = model or rec.get("llm_model")
                cost += rec.get("total_cost_usd") or 0.0
                for m, u in (rec.get("usage_by_model") or {}).items():
                    agg = by_model.setdefault(m, {})
                    for k, v in u.items():
                        if isinstance(v, (int, float)):
                            agg[k] = agg.get(k, 0) + v
            # The export lists each call twice under different call ids; key on content.
            key = (rec.get("name"), str(rec.get("arguments")), rec.get("created_at"))
            if rec.get("type") == "function_call" and key not in seen:
                seen.add(key)
                tool_calls[rec.get("name")] = tool_calls.get(rec.get("name"), 0) + 1
                leak_hits.extend(t for t in FORBIDDEN if t in str(rec.get("arguments")))
            if rec.get("type") == "function_call_output" and name == "transcript":
                for child in re.findall(r'"conversation_id": "([0-9a-f]{32})"', str(rec.get("output"))):
                    if child not in children:
                        children.append(child)

    if session:
        export(session.group(1), "transcript")
        for i, child in enumerate(children):
            export(child, f"transcript_sub{i + 1}")
    usage = {"by_model": by_model, "cost_usd": cost if session else None}

    state_dir = run_dir / "state"
    state = json.loads((state_dir / "state.json").read_text()) if (state_dir / "state.json").exists() else {}
    subs = [s for s in _jsonl(state_dir / "submissions.jsonl") if s.get("evaluated")]
    observations = _jsonl(state_dir / "observations.jsonl")
    decisions = [r for r in _jsonl(state_dir / "ledger.jsonl")
                 if r.get("kind") == "decision" and r.get("status") in ("conclude", "unresolved")]
    criteria = ("ok_delta_bic", "ok_rms", "ok_match", "ok_count")
    best = max(subs, key=lambda s: (s["success"], s["reward"]), default=None)
    tokens = {
        k: sum((m or {}).get(k, 0) or 0 for m in (usage.get("by_model") or {}).values())
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    }
    result = {
        "arm": arm,
        "task_id": task_id,
        "tier": budget["tier"],
        "difficulty": budget["difficulty"],
        "solved": bool(state.get("solved", False)),
        "submissions": len(subs),
        "submitted": bool(subs),
        "follow_up_observations": len(observations),
        "final_decision": decisions[-1]["status"] if decisions else None,
        "best_criteria": {c: bool(best["success_details"].get(c)) for c in criteria} if best else None,
        "best_match_score": best["success_details"].get("match_score") if best else None,
        "identical_resubmissions": len(subs) - len({json.dumps(s["payload"]["planets"], sort_keys=True) for s in subs}),
        "tool_calls": tool_calls,
        "sub_agent_sessions": len(children),
        "tokens": tokens,
        "cost_usd": usage.get("cost_usd"),
        "model": model,
        "duration_s": round(duration, 1),
        "timed_out": timed_out,
        "exit_code": proc.returncode,
        "session_id": session.group(1) if session else None,
        "leak_terms_in_tool_args": sorted(set(leak_hits)),
    }
    # A run that never opened a session is a harness failure, not a result: leave
    # no result.json so the next invocation retries it.
    if session:
        result_path.write_text(json.dumps(result, indent=2))
    lock.unlink(missing_ok=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--tasks", required=True, help="file with one task id per line, or comma-separated ids")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-observations", type=int, default=3)
    ap.add_argument("--max-compute-rounds", type=int, default=4)
    ap.add_argument("--prompt", default="", help="research prompt prepended to the task brief")
    ap.add_argument("--live-logs", action="store_true", help="tee Omnigent output to this terminal and run files")
    args = ap.parse_args()

    src = Path(args.tasks)
    lines = src.read_text().splitlines() if src.exists() else args.tasks.split(",")
    tasks = [t.split("#")[0].strip() for t in lines if t.split("#")[0].strip()]
    out = (REPO / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_task, args.arm, t, out, args.max_observations,
                               args.max_compute_rounds, args.prompt, args.live_logs): t for t in tasks}
        for fut in as_completed(futures):
            task_id = futures[fut]
            try:
                r = fut.result()
            except Exception as exc:
                print(f"[error] {task_id}: {exc}", file=sys.stderr, flush=True)
                continue
            if r is None:  # owned by another batch process
                continue
            results.append(r)
            print(
                f"[{len(results)}/{len(tasks)}] {r['task_id']:<18} {r['tier']:<6} "
                f"solved={r['solved']!s:<5} subs={r['submissions']} "
                f"cost=${(r['cost_usd'] or 0):.2f} {r['duration_s']:.0f}s"
                + (" TIMEOUT" if r["timed_out"] else ""),
                flush=True,
            )


if __name__ == "__main__":
    main()
