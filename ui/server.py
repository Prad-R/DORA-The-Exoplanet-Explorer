"""Small local operator UI for the existing v1 Omnigent pipeline."""
from __future__ import annotations

import argparse
import json
import mimetypes
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
STATIC = Path(__file__).with_name("static")
RUNS = REPO / "runs" / "ui"
BANKS = {
    "synthetic": REPO / "third_party" / "Stargazer" / "stargazer" / "Stargazer_synthetic_task",
    "real": REPO / "third_party" / "Stargazer" / "stargazer" / "Stargazer_real_data_task",
}
PROCESSES: dict[str, subprocess.Popen] = {}


def _tee_launcher(run_id: str, proc: subprocess.Popen, log_path: Path) -> None:
    """Persist the launcher stream while also making UI runs observable in its terminal."""
    with open(log_path, "w") as log:
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            print(f"[ui:{run_id}] {line}", end="", flush=True)
    proc.wait()


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _read_jsonl(path: Path) -> list:
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
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
        error = (root / "launcher.log").read_text(errors="replace")[-4000:] or "Run ended before a result was written."
    return {**meta, "running": running, "exit_code": None if running or proc is None else proc.returncode,
            "result": result, "error": error, "budget": _read_json(task_root / "budget.json"),
            "state": _read_json(state / "state.json"), "ledger": _read_jsonl(state / "ledger.jsonl"),
            "observations": _read_jsonl(state / "observations.jsonl"),
            "submissions": _read_jsonl(state / "submissions.jsonl")}


def start_run(payload: dict) -> dict:
    task_id = str(payload.get("task_id", ""))
    if task_path(task_id) is None:
        raise ValueError("Unknown task.")
    max_obs = int(payload.get("max_observations", 3))
    max_rounds = int(payload.get("max_compute_rounds", 4))
    if not 0 <= max_obs <= 20 or not 1 <= max_rounds <= 20:
        raise ValueError("Limits must be 0-20 observations and 1-20 compute rounds.")
    prompt = str(payload.get("prompt", "")).strip()[:4000]
    run_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    root = RUNS / run_id
    root.mkdir(parents=True)
    meta = {"run_id": run_id, "task_id": task_id, "prompt": prompt,
            "max_observations": max_obs, "max_compute_rounds": max_rounds,
            "started_at": time.time()}
    (root / "ui.json").write_text(json.dumps(meta, indent=2))
    cmd = [sys.executable, str(REPO / "runner" / "batch.py"), "--arm", "v1_lab",
           "--tasks", task_id, "--out", str(root), "--workers", "1",
           "--max-observations", str(max_obs), "--max-compute-rounds", str(max_rounds), "--live-logs"]
    if prompt:
        cmd += ["--prompt", prompt]
    proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    PROCESSES[run_id] = proc
    threading.Thread(target=_tee_launcher, args=(run_id, proc, root / "launcher.log"), daemon=True).start()
    return meta


class Handler(BaseHTTPRequestHandler):
    def _json(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/tasks":
            return self._json(task_catalog())
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
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(start_run(payload), 202)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{server.server_port}"
    print(f"Exoplanet Lab UI: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
