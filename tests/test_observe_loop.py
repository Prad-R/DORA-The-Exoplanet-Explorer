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
    monkeypatch.setenv("STARGAZER_MAX_OBSERVATIONS", "6")
    monkeypatch.setenv("STARGAZER_OBS_PER_CAMPAIGN", "4")
    monkeypatch.setenv("STARGAZER_MAX_COMPUTE_ROUNDS", "3")
    sys.modules.pop("lab.lab_server", None)
    return importlib.import_module("lab.lab_server")


def _fit(server, fit_id, bic, periods=(31.0,), rms_ok=True, strength=8.0, flags=None):
    fit = {
        "id": fit_id,
        "hypothesis_id": "H" + fit_id[1:],
        "n_planets": len(periods),
        "planets": [{
            "P_days": p, "K_ms": 4.0, "e": 0.1, "omega_rad": 0.2, "M0_rad": 0.3,
            "m_sin_i_mjup": 0.1, "l_rad": 0.5, "K_over_sigma_sqrtN": strength,
        } for p in periods],
        "rms_ms": 1.0,
        "rms_limit_ms": 2.0,
        "rms_ok": rms_ok,
        "chi2_red": 1.0,
        "bic": bic,
        "delta_bic_vs_null": 20.0,
        "flags": flags or [],
        "residuals": np.zeros(len(server.data.t)).tolist(),
        "n_obs": len(server.data.t),
    }
    (server.FITS / f"{fit_id}.json").write_text(json.dumps(fit))
    return fit


@pytest.fixture()
def quiet_residuals(server, monkeypatch):
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 0.2, "period_days": 3.0}]})


def test_unreviewed_leader_spends_nothing(server, quiet_residuals):
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 115.0, periods=(37.0,))
    result = json.loads(server.observe_or_conclude(["F1", "F2"]))
    assert result["status"] == "needs_review" and result["leader"] == "F1"
    assert server.episode.read("observations") == [] and server.episode.read("rounds") == []


def test_numerical_gate_can_conclude(server, quiet_residuals):
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 115.0, periods=(37.0,))
    server.record_verdict("F1", "approve", "independent review")

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "conclude"
    assert all(c["passed"] for c in result["checks"])
    assert server.episode.read("observations") == []


def test_small_bic_gain_from_extra_planet_does_not_take_the_lead(server, quiet_residuals):
    """A larger model must beat the smaller one by 10 in BIC; a gain of 5 is noise fitting."""
    _fit(server, "F1", 100.0, periods=(31.0, 117.0))
    _fit(server, "F2", 95.0, periods=(31.0, 117.0, 1.27))
    _fit(server, "F3", 600.0, periods=(117.0,))
    server.record_verdict("F1", "approve", "simplest adequate model")

    result = json.loads(server.observe_or_conclude(["F1", "F2", "F3"]))

    assert result["status"] == "conclude" and result["leader"] == "F1"
    assert result["larger_models_not_needed"] == ["F2"]


def test_leftover_signal_asks_for_analysis_not_data(server, monkeypatch):
    monkeypatch.setattr(server.rv, "periodogram", lambda *a, **k: {"peaks": [{"fap": 1e-6, "period_days": 8.0}]})
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 140.0, periods=(37.0,))
    server.record_verdict("F1", "approve", "reviewed")

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "refine"
    assert server.episode.read("observations") == []


def test_ambiguous_models_trigger_a_multi_point_campaign(server, quiet_residuals):
    before = len(server.data.t)
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 104.0, periods=(37.0,))  # same planet count, BIC within 10: an alias is possible
    server.record_verdict("F1", "approve", "reviewed")

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "observe"
    times = result["campaign"]["times_days"]
    assert len(times) == 4 and len(server.data.t) == before + 4
    assert min(np.diff(times)) >= 0.5  # one point per night
    assert all(set(o) == {"time_days", "rv_ms", "sigma_ms", "instrument", "kind"} for o in result["observations"])
    assert set(result["refits"]) == {"F1", "F2"}
    assert json.loads(server.task_summary())["follow_up_points_left"] == 2


def test_stale_fits_are_refitted_before_deciding(server, quiet_residuals):
    _fit(server, "F1", 100.0)
    _fit(server, "F2", 104.0, periods=(37.0,))
    server.episode.simulate_observation(float(server.data.t.max()) + 3.0, 1.0, "instA")

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "refitted" and set(result["refits"]) == {"F1", "F2"}
    new = server._load_fit(result["refits"]["F1"])
    assert new["n_obs"] == len(server.data.t) and new["refit_of"] == "F1"


def test_other_processes_see_new_observations(server, tmp_path):
    from lab.episode import Episode

    other = Episode("seed96_diff3", tmp_path)  # another agent's tool server
    n = len(other.times)
    server.episode.simulate_observation(float(server.data.t.max()) + 3.0, 1.0, "instA")
    assert other.reload_observations() and len(other.times) == n + 1
    assert not other.reload_observations()


def test_simulated_observations_follow_the_task_signal(tmp_path):
    """Follow-ups taken at the original times must reproduce the original data to the noise level."""
    from lab.episode import Episode

    ep = Episode("seed96_diff3", tmp_path)
    # Spread across the whole baseline so a phase error cannot hide.
    t, y = ep.times[::6].copy(), ep.rvs[::6].copy()
    noise = float(np.hypot(np.median(ep.sigmas), ep.task.config.noise.sigma_jitter_ms))
    sim = np.array([ep.simulate_observation(float(ti), float(np.median(ep.sigmas)), "instA")["rv_ms"] for ti in t])
    # Each point carries two independent noise draws (original and simulated).
    assert np.sqrt(np.mean((sim - y) ** 2)) < 2 * np.sqrt(2) * noise
    assert np.std(sim) > 10  # the signal (K ~ 14 and 29 m/s) must vary with time


def test_observation_budget_returns_unresolved(server, quiet_residuals, monkeypatch):
    monkeypatch.setenv("STARGAZER_MAX_OBSERVATIONS", "0")
    _fit(server, "F1", 100.0, strength=2.0)
    _fit(server, "F2", 130.0, periods=(37.0,))
    server.record_verdict("F1", "approve", "reviewed")

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "unresolved"
    assert server.episode.read("observations") == []


def test_real_data_never_invokes_simulator(server, quiet_residuals, monkeypatch):
    _fit(server, "F1", 100.0, strength=2.0)
    _fit(server, "F2", 130.0, periods=(37.0,))
    server.record_verdict("F1", "approve", "reviewed")
    monkeypatch.setattr(server.episode, "task_id", "real_example")
    monkeypatch.setattr(server.episode, "simulate_observation",
                        lambda *a, **k: pytest.fail("simulator must not be called"))

    result = json.loads(server.observe_or_conclude(["F1", "F2"]))

    assert result["status"] == "unresolved"
    assert "disabled" in result["summary"]
