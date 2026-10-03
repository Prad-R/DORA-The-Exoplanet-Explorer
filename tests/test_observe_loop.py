"""Focused checks for the autonomous observe-or-conclude extension."""
import importlib
import json
import sys
import types

import numpy as np
import pytest

# The production harness is Linux/Omnigent. Keep these focused unit tests
# runnable on development machines that lack its fcntl and MCPServer shims.
try:
    import fcntl  # noqa: F401
except ImportError:
    fcntl = types.ModuleType("fcntl")
    fcntl.LOCK_EX, fcntl.LOCK_UN = 1, 2
    fcntl.flock = lambda *args: None
    sys.modules["fcntl"] = fcntl

try:
    from mcp.server.mcpserver import MCPServer  # noqa: F401
except ImportError:
    shim = types.ModuleType("mcp.server.mcpserver")

    class MCPServer:
        def __init__(self, name):
            self.name = name

        def tool(self):
            return lambda fn: fn

    shim.MCPServer = MCPServer
    sys.modules["mcp.server.mcpserver"] = shim


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("STARGAZER_TASK", "seed96_diff3")
    monkeypatch.setenv("STARGAZER_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("STARGAZER_MAX_OBSERVATIONS", "2")
    monkeypatch.setenv("STARGAZER_MAX_COMPUTE_ROUNDS", "3")
    sys.modules.pop("lab.lab_server", None)
    return importlib.import_module("lab.lab_server")


def _fit(server, fit_id, bic, rms_ok=True, strength=8.0, flags=None):
    fit = {
        "id": fit_id,
        "hypothesis_id": "H" + fit_id[1:],
        "n_planets": 1,
        "planets": [{
            "P_days": 31.0 if fit_id == "F1" else 37.0,
            "K_ms": 4.0,
            "e": 0.1,
            "omega_rad": 0.2,
            "M0_rad": 0.3,
            "m_sin_i_mjup": 0.1,
            "l_rad": 0.5,
            "K_over_sigma_sqrtN": strength,
        }],
        "rms_ms": 1.0,
        "rms_limit_ms": 2.0,
        "rms_ok": rms_ok,
        "chi2_red": 1.0,
        "bic": bic,
        "delta_bic_vs_null": 20.0,
        "flags": flags or [],
        "residuals": np.zeros(len(server.data.t)).tolist(),
    }
    (server.FITS / f"{fit_id}.json").write_text(json.dumps(fit))
    return fit


def test_numerical_gate_can_conclude(server, monkeypatch):
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 115.0)
    server.record_verdict("F1", "approve", "independent review")
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 0.2}]})

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "conclude"
    assert result["evidence"]["criteria"] == {k: True for k in result["evidence"]["criteria"]}
    assert server.episode.read("observations") == []


def test_observe_updates_dataset_without_exposing_truth(server, monkeypatch):
    before = len(server.data.t)
    _fit(server, "F1", 100.0, strength=2.0)
    _fit(server, "F2", 102.0)
    server.record_verdict("F1", "approve", "reviewed")
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 0.2}]})

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "observe"
    assert len(server.data.t) == before + 1
    assert set(result["observation"]) == {"time_days", "rv_ms", "sigma_ms", "instrument", "kind"}
    assert not ({"planets", "truth", "config"} & set(result["observation"]))
    assert json.loads(server.task_summary())["n_obs"] == before + 1


def test_observation_budget_returns_unresolved(server, monkeypatch):
    monkeypatch.setenv("STARGAZER_MAX_OBSERVATIONS", "0")
    _fit(server, "F1", 100.0, rms_ok=False)
    _fit(server, "F2", 101.0)
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 1e-6}]})

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "unresolved"
    assert server.episode.read("observations") == []


def test_real_data_never_invokes_simulator(server, monkeypatch):
    _fit(server, "F1", 100.0, rms_ok=False)
    _fit(server, "F2", 101.0)
    monkeypatch.setattr(server.episode, "task_id", "real_example")
    monkeypatch.setattr(server.episode, "simulate_observation",
                        lambda *a, **k: pytest.fail("simulator must not be called"))
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 1e-6}]})

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "unresolved"
    assert "disabled" in result["reason"]
