"""Harness checks that need no LLM: truth passes, replay is counted, REPL is fenced."""
import importlib
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows locking regression")
def test_windows_episode_lock_releases_cleanly(tmp_path):
    code = (
        "from pathlib import Path; "
        "from lab.episode import Episode; "
        f"Episode('seed96_diff3', Path({str(tmp_path)!r})); "
        "print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGAZER_TASK", "seed96_diff3")
    monkeypatch.setenv("STARGAZER_RUN_DIR", str(tmp_path))
    sys.modules.pop("lab.mcp_server", None)
    return importlib.import_module("lab.mcp_server")


def _truth(server):
    return [
        {"P_days": p.P_days, "m_sin_i_mjup": p.m_sin_i_mjup, "e": p.e,
         "omega_rad": p.omega_rad, "l_rad": p.l_rad}
        for p in server.episode.task.config.planets
    ]


def test_submit_blocked_until_guide_ack(server):
    assert "blocked" in server.submit_action(planets=_truth(server))
    assert server.episode.state()["submissions"] == 0


def test_truth_passes_all_criteria(server):
    server.PythonREPL("_protocol_guide_ack = True")
    out = server.submit_action(planets=_truth(server))
    state = server.episode.state()
    assert state["solved"] and state["submissions"] == 1, out[:800]


def test_submission_cap(server):
    server.PythonREPL("_protocol_guide_ack = True")
    wrong = [{"P_days": 3.0, "m_sin_i_mjup": 0.01, "e": 0.0, "omega_rad": 0.0, "l_rad": 0.0}]
    cap = server.episode.budget["max_submissions"]
    for _ in range(cap):
        server.submit_action(planets=wrong)
    assert "no submissions left" in server.submit_action(planets=wrong)
    assert server.episode.state()["submissions"] == cap


def test_repl_keeps_state_and_refuses_benchmark_internals(server):
    server.PythonREPL("x = len(times_days)")
    assert server.PythonREPL("print(x)").strip() == str(len(server.episode.times))
    assert "rejected" in server.PythonREPL("import os; print(os.environ)")


def test_policies_gate_submissions(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGAZER_TASK", "seed96_diff3")
    monkeypatch.setenv("STARGAZER_RUN_DIR", str(tmp_path))
    sys.modules.pop("lab.lab_server", None)
    lab = importlib.import_module("lab.lab_server")
    from lab.policies import no_repeat_submission, require_review

    def call(fit_id):
        return {"type": "tool_call", "data": {"name": "lab__submit_fit", "arguments": {"fit_id": fit_id}}}

    review, repeat = require_review(str(tmp_path)), no_repeat_submission(str(tmp_path))
    lab.propose_hypothesis([105.0], "one planet only")
    lab.fit_hypothesis("H1")
    assert review(call("F1"))["result"] == "DENY"
    lab.record_verdict("F1", "approve", "test")
    assert review(call("F1"))["result"] == "ALLOW"
    assert repeat(call("F1"))["result"] == "ALLOW"

    lab.submit_fit("F1", "information-gathering")  # wrong planet count: fails
    lab.fit_hypothesis("H1")  # same configuration again
    assert repeat(call("F2"))["result"] == "DENY"

    lab.propose_hypothesis([117.0, 31.0], "two planets")
    lab.fit_hypothesis("H2")
    assert repeat(call("F3"))["result"] == "ALLOW"
    lab.submit_fit("F3", "two-planet model")
    assert lab.episode.state()["solved"]
    kinds = [r["kind"] for r in lab.episode.read("ledger")]
    assert kinds.count("submission") == 2 and kinds.count("fit") == 3
