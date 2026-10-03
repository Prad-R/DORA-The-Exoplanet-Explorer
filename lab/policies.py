"""Omnigent policies for the lab arm. Standard library only: they are imported
by the Omnigent runner, not by the lab's own environment.

Sub-agents run in separate sessions, so the state these policies check is the
run directory's research record rather than per-session policy state.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

Event = Dict[str, Any]
Response = Optional[Dict[str, Any]]


def _jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _submit_fit_id(event: Event) -> Optional[str]:
    """The fit id if this event is a call to submit_fit, else None."""
    if event.get("type") != "tool_call":
        return None
    data = event.get("data") or {}
    if not str(data.get("name", "")).endswith("submit_fit"):
        return None
    return str((data.get("arguments") or {}).get("fit_id", ""))


def _fit_periods(run_dir: Path, fit_id: str) -> Optional[List[float]]:
    path = run_dir / "fits" / f"{fit_id}.json"
    if not path.exists():
        return None
    return sorted(p["P_days"] for p in json.loads(path.read_text())["planets"])


def no_repeat_submission(run_dir: str, period_tolerance: float = 0.01) -> Callable[[Event], Response]:
    """DENY a submission that repeats a configuration the evaluator already failed:
    same number of planets with every period within ``period_tolerance``."""
    root = Path(run_dir)

    def evaluate(event: Event) -> Response:
        fit_id = _submit_fit_id(event)
        periods = _fit_periods(root, fit_id) if fit_id else None
        if periods is None:
            return None
        for sub in _jsonl(root / "submissions.jsonl"):
            if not sub.get("evaluated") or sub.get("success"):
                continue
            prev = sorted(p["P_days"] for p in sub["payload"]["planets"])
            if len(prev) == len(periods) and all(
                abs(math.log(a / b)) < period_tolerance for a, b in zip(periods, prev)
            ):
                return {
                    "result": "DENY",
                    "reason": (
                        f"{fit_id} repeats a configuration that already failed "
                        f"({len(prev)} planet(s), periods {[round(p, 2) for p in prev]} d). "
                        "Submit a different hypothesis: change the planet count or swap a period "
                        "for its alias or harmonic."
                    ),
                }
        return {"result": "ALLOW"}

    return evaluate


def require_review(run_dir: str) -> Callable[[Event], Response]:
    """DENY a submission of a fit that the critic has not reviewed."""
    root = Path(run_dir)

    def evaluate(event: Event) -> Response:
        fit_id = _submit_fit_id(event)
        if not fit_id or _fit_periods(root, fit_id) is None:
            return None
        reviewed = any(
            r.get("kind") == "verdict" and r.get("fit_id") == fit_id for r in _jsonl(root / "ledger.jsonl")
        )
        if reviewed:
            return {"result": "ALLOW"}
        return {
            "result": "DENY",
            "reason": f"{fit_id} has no critic verdict in the research record. Dispatch the critic on it first.",
        }

    return evaluate


def approve_last_submission(run_dir: str, max_submissions: int, enabled: bool = False) -> Callable[[Event], Response]:
    """ASK the human before the final submission is spent (interactive sessions only)."""
    root = Path(run_dir)

    def evaluate(event: Event) -> Response:
        if not enabled or not _submit_fit_id(event):
            return None
        state_path = root / "state.json"
        used = json.loads(state_path.read_text())["submissions"] if state_path.exists() else 0
        if max_submissions - used == 1:
            return {"result": "ASK", "reason": "This is the last submission for this star. Approve spending it?"}
        return {"result": "ALLOW"}

    return evaluate
