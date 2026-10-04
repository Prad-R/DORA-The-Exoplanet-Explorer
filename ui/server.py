"""Small local operator UI for the existing v1 Omnigent pipeline."""
from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from lab.report import describe  # noqa: E402

STATIC = Path(__file__).with_name("static")
RUNS = REPO / "runs" / "ui"
BANKS = {
    "synthetic": REPO / "third_party" / "Stargazer" / "stargazer" / "Stargazer_synthetic_task",
    "real": REPO / "third_party" / "Stargazer" / "stargazer" / "Stargazer_real_data_task",
}
PROCESSES: dict[str, subprocess.Popen] = {}

def _access_key() -> str:
    """Key remote callers must send as X-Lab-Key; created once and kept in runs/ (gitignored)."""
    path = REPO / "runs" / "ui-access-key.txt"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_urlsafe(18), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


ACCESS_KEY = os.environ.get("LAB_ACCESS_KEY") or _access_key()
ALLOWED_ORIGIN = re.compile(
    r"^(https://[a-z0-9-]+(\.[a-z0-9-]+)*\.(lovable\.app|lovableproject\.com|lovable\.dev)"
    r"|http://(localhost|127\.0\.0\.1)(:\d+)?)$")


def _tee_launcher(run_id: str, proc: subprocess.Popen, log_path: Path) -> None:
    """Persist the launcher stream while also making UI runs observable in its terminal."""
    with open(log_path, "w", encoding="utf-8") as log:
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(f"[ui:{run_id}] {line}", end="", flush=True)
    proc.wait()


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _read_jsonl(path: Path) -> list:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def task_path(task_id: str) -> Path | None:
    if not task_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in task_id):
        return None
    bank = BANKS["real" if task_id.startswith("real_") else "synthetic"]
    path = bank / f"{task_id}.json"
    return path if path.exists() else None


def task_catalog() -> list[dict]:
    rows = []
    for bank, root in BANKS.items():
        for path in sorted(root.glob("*.json")):
            data = _read_json(path, {})
            obs = data.get("observations", {})
            times = obs.get("times_days", [])
            if not times:
                continue
            rows.append({"id": path.stem, "bank": bank, "difficulty": data.get("truth_difficulty"),
                         "n_obs": len(times), "baseline_days": round(max(times) - min(times), 2)})
    return rows


def task_preview(task_id: str) -> dict | None:
    path = task_path(task_id)
    if not path:
        return None
    data = _read_json(path, {})
    obs = data.get("observations", {})
    return {"id": task_id, "difficulty": data.get("truth_difficulty"), "observations": obs,
            "star_mass_sun": data.get("config", {}).get("star", {}).get("M_star_sun")}


def run_snapshot(run_id: str) -> dict | None:
    if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in run_id):
        return None
    root = RUNS / run_id
    meta = _read_json(root / "ui.json")
    if meta is None:
        return None
    task_id = meta["task_id"]
    task_root, state = root / task_id, root / task_id / "state"
    proc = PROCESSES.get(run_id)
    running = proc is not None and proc.poll() is None
    result = _read_json(task_root / "result.json")
    error = None
    if proc is not None and not running and result is None:
        error = (root / "launcher.log").read_text(encoding="utf-8", errors="replace")[-4000:] or "Run ended before a result was written."
    ledger = _read_jsonl(state / "ledger.jsonl")
    return {**meta, "running": running, "exit_code": None if running or proc is None else proc.returncode,
            "result": result, "error": error, "budget": _read_json(task_root / "budget.json"),
            "state": _read_json(state / "state.json"), "ledger": ledger,
            # Plain-language rendering of each record entry, shared with report.md.
            "entries": [describe(r) for r in ledger],
            "final_report": (result or {}).get("final_report"),
            "observations": _read_jsonl(state / "observations.jsonl"),
            "submissions": _read_jsonl(state / "submissions.jsonl")}


def run_list() -> list[dict]:
    """Past and current UI runs, newest first, with their outcome."""
    rows = []
    for root in sorted(RUNS.glob("*/ui.json"), reverse=True):
        meta = _read_json(root, {})
        result = _read_json(root.parent / meta.get("task_id", "") / "result.json") or {}
        proc = PROCESSES.get(meta.get("run_id"))
        rows.append({**{k: meta.get(k) for k in ("run_id", "task_id", "started_at")},
                     "running": proc is not None and proc.poll() is None,
                     **{k: result.get(k) for k in ("solved", "final_decision", "submissions",
                                                   "follow_up_observations", "duration_s", "cost_usd")}})
    return rows


def start_run(payload: dict) -> dict:
    task_id = str(payload.get("task_id", ""))
    if task_path(task_id) is None:
        raise ValueError("Unknown task.")
    max_obs = int(payload.get("max_observations", 30))
    per_campaign = int(payload.get("obs_per_campaign", 10))
    max_rounds = int(payload.get("max_compute_rounds", 4))
    if not 0 <= max_obs <= 200 or not 1 <= per_campaign <= 50 or not 1 <= max_rounds <= 20:
        raise ValueError("Limits: 0-200 follow-up points, 1-50 per campaign, 1-20 decision rounds.")
    prompt = str(payload.get("prompt", "")).strip()[:4000]
    run_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    root = RUNS / run_id
    root.mkdir(parents=True)
    meta = {"run_id": run_id, "task_id": task_id, "prompt": prompt,
            "max_observations": max_obs, "obs_per_campaign": per_campaign, "max_compute_rounds": max_rounds,
            "started_at": time.time()}
    (root / "ui.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    cmd = [sys.executable, str(REPO / "runner" / "batch.py"), "--arm", "v1_lab",
           "--tasks", task_id, "--out", str(root), "--workers", "1",
           "--max-observations", str(max_obs), "--obs-per-campaign", str(per_campaign),
           "--max-compute-rounds", str(max_rounds), "--live-logs"]
    if prompt:
        cmd += ["--prompt", prompt]
    proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace")
    PROCESSES[run_id] = proc
    threading.Thread(target=_tee_launcher, args=(run_id, proc, root / "launcher.log"), daemon=True).start()
    return meta


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        """Let the Lovable-hosted front end (and local dev servers) call this API.

        Only these origins: the API can start paid runs, so an arbitrary site must not.
        """
        origin = self.headers.get("Origin", "")
        if ALLOWED_ORIGIN.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Lab-Key")
            # Chrome's Private/Local Network Access preflight for public page -> localhost.
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _authorized(self) -> bool:
        """Local use needs no key; anything via the tunnel or another site's page does.

        The tunnel connects from localhost too, so locality is judged by the
        forwarding headers it adds and by the page's Origin, not the socket address.
        """
        forwarded = any(self.headers.get(h) for h in ("Cf-Connecting-Ip", "X-Forwarded-For", "Forwarded"))
        origin = self.headers.get("Origin", "")
        local_origin = not origin or re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", origin)
        if not forwarded and local_origin:
            return True
        return hmac.compare_digest(self.headers.get("X-Lab-Key", ""), ACCESS_KEY)

    def _json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/") and not self._authorized():
            return self._json({"error": "Missing or wrong access key."}, 401)
        if path == "/api/tasks":
            return self._json(task_catalog())
        if path == "/api/runs":
            return self._json(run_list())
        if path.startswith("/api/tasks/"):
            value = task_preview(path.removeprefix("/api/tasks/"))
            return self._json(value or {"error": "Not found"}, 200 if value else 404)
        if path.startswith("/api/runs/"):
            value = run_snapshot(path.removeprefix("/api/runs/"))
            return self._json(value or {"error": "Not found"}, 200 if value else 404)
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        file = (STATIC / relative).resolve()
        if STATIC.resolve() not in file.parents or not file.is_file():
            return self._json({"error": "Not found"}, 404)
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/runs":
            return self._json({"error": "Not found"}, 404)
        if not self._authorized():
            return self._json({"error": "Missing or wrong access key."}, 401)
        # One run at a time: each run spends the host's model credits.
        if any(p.poll() is None for p in PROCESSES.values()):
            return self._json({"error": "A run is already in progress. Wait for it to finish."}, 409)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(start_run(payload), 202)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)

    def log_message(self, format, *args):
        return


def stop_stale_omnigent() -> None:
    """Stop Omnigent hosts left by an earlier UI process.

    A host outlives the UI that started it; once that UI's console is gone, the
    runners it launches die at startup (Windows 0xC0000142). Runs keep Omnigent
    state in .omnigent-runtime (see runner/batch.py), so stop it there.
    """
    omnigent = shutil.which("omnigent")
    if not omnigent:
        return
    runtime = str(REPO / ".omnigent-runtime")
    env = {**os.environ, "OMNIGENT_DATA_DIR": runtime, "OMNIGENT_CONFIG_HOME": runtime}
    out = subprocess.run([omnigent, "stop"], env=env, capture_output=True, encoding="utf-8", errors="replace")
    print(f"Omnigent cleanup: {(out.stdout or out.stderr).strip() or 'done'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Relayed run output is UTF-8; a cp1252 console would raise in the tee thread.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    stop_stale_omnigent()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{server.server_port}"
    print(f"Exoplanet Lab UI: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
