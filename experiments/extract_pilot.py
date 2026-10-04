"""Extract the pilot runs into tables, next to main's runs of the same tasks.

    python experiments/extract_pilot.py

Writes experiments/pilot/runs.csv (one row per run), fits.csv (every fit the lab
made, scored offline against the truth) and timeline.csv (the lab's research
record in order). Offline scoring calls Stargazer's evaluator in a scratch
directory; it spends no submissions and no model calls.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lab import rv  # noqa: E402
from lab.episode import Episode  # noqa: E402

OUT = REPO / "experiments" / "pilot"
# (label, task, arm, source): source is a run directory here or a path on main.
RUNS = [
    ("this branch: plain agent", "seed44_diff2", "v0", REPO / "runs/smoke/seed44_diff2"),
    ("main: plain agent", "seed44_diff2", "v0", "runs/v0/seed44_diff2"),
    ("main: lab, no observing", "seed44_diff2", "v1", "runs/v1/seed44_diff2"),
    ("this branch: lab with observing", "seed15_diff5", "v1", REPO / "runs/v1_obs/seed15_diff5"),
    ("main: plain agent", "seed15_diff5", "v0", "runs/v0/seed15_diff5"),
]


def _from_main(path: str) -> str:
    return subprocess.run(["git", "show", f"main:{path}"], cwd=REPO, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def _jsonl(text: str) -> list:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _read(src, name: str) -> str:
    if isinstance(src, Path):
        p = src / name
        return p.read_text(encoding="utf-8") if p.exists() else ""
    try:
        return _from_main(f"{src}/{name}")
    except subprocess.CalledProcessError:
        return ""


def run_rows() -> list:
    rows = []
    for label, task, arm, src in RUNS:
        r = json.loads(_read(src, "result.json"))
        subs = [s for s in _jsonl(_read(src, "state/submissions.jsonl")) if s.get("evaluated")]
        crit = r.get("best_criteria") or {}
        tok = r.get("tokens") or {}
        rows.append({
            "run": label, "task": task, "arm": arm, "tier": r["tier"], "difficulty": r["difficulty"],
            "solved": r["solved"], "submissions": r["submissions"],
            "match_scores": " / ".join(f"{(s['success_details'] or {}).get('match_score', 0):.3f}" for s in subs),
            "ok_rms": crit.get("ok_rms"), "ok_delta_bic": crit.get("ok_delta_bic"),
            "ok_count": crit.get("ok_count"), "ok_match": crit.get("ok_match"),
            "follow_up_points": r.get("follow_up_observations", 0),
            "observing_campaigns": r.get("observing_campaigns", 0),
            "sub_agent_sessions": r.get("sub_agent_sessions", 0),
            "tool_calls": sum((r.get("tool_calls") or {}).values()),
            "output_tokens": tok.get("output_tokens"), "cache_read_tokens": tok.get("cache_read_input_tokens"),
            "cost_usd": round(r["cost_usd"] or 0, 3), "duration_s": r["duration_s"], "timed_out": r["timed_out"],
            "model": r["model"],
        })
    return rows


def fit_rows(run_dir: Path, task: str) -> list:
    """Every fit the lab made, with what the evaluator would have said had it been submitted."""
    state = run_dir / "state"
    verdicts = {}
    for rec in _jsonl((state / "ledger.jsonl").read_text(encoding="utf-8")):
        if rec["kind"] == "verdict":
            verdicts.setdefault(rec["fit_id"], []).append(rec["verdict"])
    submitted = {s["fit_id"] for s in _jsonl((state / "ledger.jsonl").read_text(encoding="utf-8"))
                 if s["kind"] == "submission"}
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in sorted((state / "fits").glob("F*.json"), key=lambda p: int(p.stem[1:])):
            fit = json.loads(path.read_text(encoding="utf-8"))
            ep = Episode(task, Path(tmp) / fit["id"])
            ep.submit(rv.submission_payload(fit))
            d = ep.read("submissions")[-1]["success_details"] or {}
            rows.append({
                "fit": fit["id"], "hypothesis": fit.get("hypothesis_id"), "refit_of": fit.get("refit_of"),
                "n_obs": fit.get("n_obs"), "n_planets": fit["n_planets"],
                "periods_days": " + ".join(f"{p['P_days']:.2f}" for p in fit["planets"]),
                "rms_ms": round(fit["rms_ms"], 3), "rms_ok": fit["rms_ok"], "bic": round(fit["bic"], 1),
                "critic": " / ".join(verdicts.get(fit["id"], [])), "submitted": fit["id"] in submitted,
                "offline_match_score": round(d.get("match_score", 0), 3),
                "offline_ok_count": d.get("ok_count"), "offline_ok_match": d.get("ok_match"),
                "offline_would_pass": all(d.get(k) for k in ("ok_rms", "ok_delta_bic", "ok_count", "ok_match")),
            })
    return rows


def timeline_rows(run_dir: Path) -> list:
    t0 = None
    rows = []
    for i, rec in enumerate(_jsonl((run_dir / "state" / "ledger.jsonl").read_text(encoding="utf-8")), 1):
        t0 = t0 or rec["t"]
        kind = rec["kind"]
        if kind == "hypothesis":
            text = f"{rec['id']}: periods {rec['periods_days']}"
        elif kind == "fit":
            text = f"{rec['id']}: {rec['n_planets']} planet(s), periods " \
                   f"{[round(p['P_days'], 2) for p in rec['planets']]}, n_obs {rec.get('n_obs')}"
        elif kind == "verdict":
            text = f"{rec['verdict']} {rec['fit_id']}: {rec['reasons']}"
        elif kind == "submission":
            text = f"{rec['fit_id']} success={rec['success']} {rec['criteria']}"
        elif kind == "decision" and "status" in rec:
            text = f"[{rec['status']}] {rec['summary']}"
        else:
            text = rec.get("text", "")
        rows.append({"step": i, "seconds": round(rec["t"] - t0), "kind": kind,
                     "status": rec.get("status", ""), "text": " ".join(text.split())})
    return rows


def _write(name: str, rows: list) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    lab_run = REPO / "runs/v1_obs/seed15_diff5"
    _write("runs.csv", run_rows())
    _write("fits.csv", fit_rows(lab_run, "seed15_diff5"))
    _write("timeline.csv", timeline_rows(lab_run))
    obs = _jsonl((lab_run / "state" / "observations.jsonl").read_text(encoding="utf-8"))
    _write("observations.csv", [{k: r[k] for k in ("time_days", "rv_ms", "sigma_ms", "instrument")} for r in obs])
    print(f"Wrote {OUT.relative_to(REPO)}: runs.csv, fits.csv, timeline.csv, observations.csv")
