"""Lab tool server (stdio MCP) for the v1 multi-agent arm.

Every sub-agent session starts its own copy of this server, so all shared
state (hypotheses, fits, verdicts, submissions) lives in the run directory and
is exposed as one research record through ``ledger``.

Configured by environment: STARGAZER_TASK, STARGAZER_RUN_DIR.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np
try:  # MCP <1.0 exposed MCPServer; current MCP uses FastMCP.
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from lab import rv
from lab.episode import FORBIDDEN, from_env

from stargazer.agents.tools.python_repl_tool import _ThreadLocalStdoutProxy, execute_python_repl

mcp = MCPServer("lab")
episode = from_env()
data = rv.Data(episode.times, episode.rvs, episode.sigmas, np.asarray(episode.instruments), episode.star_mass_sun)
FITS = episode.run_dir / "fits"
FITS.mkdir(exist_ok=True)


def _load_fit(fit_id: str) -> Optional[Dict[str, Any]]:
    path = FITS / f"{fit_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _fit_view(fit: Dict[str, Any]) -> Dict[str, Any]:
    """What an agent sees of a fit: everything except the residual array."""
    view = {k: v for k, v in fit.items() if k != "residuals"}
    view["planets"] = [
        {k: round(float(v), 5) for k, v in p.items() if k in ("P_days", "K_ms", "e", "omega_rad", "K_over_sigma_sqrtN")}
        for p in fit["planets"]
    ]
    return view


def _refresh_data() -> None:
    """Refresh this server after Episode persisted a follow-up observation."""
    global data
    data = rv.Data(episode.times, episode.rvs, episode.sigmas, np.asarray(episode.instruments), episode.star_mass_sun)
    repl_globals.update(times_days=data.t, rvs_ms=data.y, sigmas_ms=data.s, instruments=data.inst)


def _fit_model(fit: Dict[str, Any], times: np.ndarray) -> np.ndarray:
    return np.sum(
        [rv.planet_rv(times, data.t[0], p) for p in fit["planets"]], axis=0
    ) if fit["planets"] else np.zeros_like(times)


@mcp.tool()
def task_summary() -> str:
    """Dataset facts and what is left of the budget."""
    max_observations = int(os.environ.get("STARGAZER_MAX_OBSERVATIONS", "3"))
    max_rounds = int(os.environ.get("STARGAZER_MAX_COMPUTE_ROUNDS", "4"))
    return json.dumps(
        {
            "n_obs": len(data.t),
            "baseline_days": round(data.span, 2),
            "median_sigma_ms": round(float(np.median(data.s)), 3),
            "rv_range_ms": [round(float(data.y.min()), 2), round(float(data.y.max()), 2)],
            "instruments": sorted(set(episode.instruments)),
            "star_mass_sun": data.star_mass_sun,
            "pass_criteria": "RMS <= 1.5 x median sigma, model preferred over a constant by BIC, "
            "correct planet count, and orbital parameters close to the true ones",
            "submissions_left": episode.submissions_left(),
            "follow_up_observations_left": max(0, max_observations - len(episode.read("observations"))),
            "compute_rounds_left": max(0, max_rounds - len(episode.read("observe_decisions"))),
            "seconds_left": int(episode.time_left()),
        }
    )


@mcp.tool()
def periodogram(residuals_of_fit: Optional[str] = None, top_k: int = 6) -> str:
    """Generalised Lomb-Scargle peaks of the data, or of the residuals of a fit ID.

    Each peak carries its false-alarm probability, the peaks it is a harmonic of,
    and its sampling aliases (periods that the observing cadence makes look alike).
    """
    resid = None
    if residuals_of_fit:
        fit = _load_fit(residuals_of_fit)
        if fit is None:
            return f"Unknown fit id {residuals_of_fit!r}."
        resid = np.asarray(fit["residuals"])
    return json.dumps(rv.periodogram(data, resid=resid, top_k=top_k))


@mcp.tool()
def propose_hypothesis(periods_days: List[float], rationale: str) -> str:
    """Register a candidate planetary system (one starting period per planet; an
    empty list is the no-planet hypothesis). Returns its hypothesis ID."""
    hid = episode.next_id("H")
    episode.append("ledger", {"kind": "hypothesis", "id": hid, "periods_days": periods_days,
                              "rationale": rationale, "label": "agent-generated hypothesis"})
    return f"{hid} registered with {len(periods_days)} planet(s)."


@mcp.tool()
def fit_hypothesis(hypothesis_id: str, period_tolerance: float = 0.1) -> str:
    """Fit Keplerian orbits for a hypothesis by global optimisation and return the fit.

    Periods may move by ``period_tolerance`` (fractional) from the hypothesis's
    starting values. The result includes RMS against the pass limit, BIC, and
    flags for periods stuck on a bound, extreme eccentricity, or near-equal periods.
    """
    hyp = next((r for r in episode.read("ledger") if r["kind"] == "hypothesis" and r["id"] == hypothesis_id), None)
    if hyp is None:
        return f"Unknown hypothesis id {hypothesis_id!r}."
    fit = rv.fit_keplerians(data, hyp["periods_days"], period_tolerance=min(max(period_tolerance, 0.005), 0.5))
    fid = episode.next_id("F")
    fit.update({"id": fid, "hypothesis_id": hypothesis_id, "period_tolerance": period_tolerance})
    (FITS / f"{fid}.json").write_text(json.dumps(fit))
    view = _fit_view(fit)
    episode.append("ledger", {"kind": "fit", **view})
    return json.dumps(view)


@mcp.tool()
def record_verdict(fit_id: str, verdict: str, reasons: str) -> str:
    """Record an independent review of a fit: verdict is 'approve' or 'reject'."""
    if _load_fit(fit_id) is None:
        return f"Unknown fit id {fit_id!r}."
    if verdict not in ("approve", "reject"):
        return "verdict must be 'approve' or 'reject'."
    episode.append("ledger", {"kind": "verdict", "fit_id": fit_id, "verdict": verdict, "reasons": reasons})
    return f"Verdict on {fit_id} recorded: {verdict}."


@mcp.tool()
def note(kind: str, text: str) -> str:
    """Add an entry to the research record. kind: 'evidence', 'plan' or 'decision'."""
    if kind not in ("evidence", "plan", "decision"):
        return "kind must be 'evidence', 'plan' or 'decision'."
    episode.append("ledger", {"kind": kind, "text": text})
    return "Recorded."


@mcp.tool()
def ledger() -> str:
    """The shared research record: evidence, hypotheses, fits, verdicts, plans,
    decisions and submission feedback, in order."""
    return json.dumps([{k: v for k, v in r.items() if k != "t"} for r in episode.read("ledger")])


def _next_step(details: Dict[str, Any]) -> str:
    """Map the evaluator's per-criterion result to what it implies."""
    if not details.get("ok_rms") or not details.get("ok_delta_bic"):
        return "The model does not fit the data well enough: refit, or a signal is missing."
    if not details.get("ok_count"):
        return ("The fit is good but the number of planets is wrong: test hypotheses with one more "
                "and one fewer planet. Do not resubmit this configuration.")
    if not details.get("ok_match"):
        return ("The fit is good and the count is right, but the orbits are not the true ones: a period "
                "is likely an alias or harmonic, or an amplitude or eccentricity is off. Test the alias "
                "and harmonic alternatives of each period. Do not resubmit this configuration.")
    return "All criteria passed."


@mcp.tool()
def submit_fit(fit_id: str, rationale: str) -> str:
    """Spend one submission on a fit. The server builds the submission from the
    stored fit, so no parameter conversion is needed. Returns per-criterion feedback."""
    fit = _load_fit(fit_id)
    if fit is None:
        return f"Unknown fit id {fit_id!r}."
    if not fit["planets"]:
        return "Cannot submit a fit with no planets."
    before = episode.state()["submissions"]
    episode.submit({**rv.submission_payload(fit), "notes": rationale})
    last = episode.read("submissions")[-1]
    if episode.state()["submissions"] == before:
        return last["feedback"]
    details = last["success_details"]
    # Stargazer's feedback also carries each planet's distance from the truth.
    # The lab sees only pass/fail per criterion, so it cannot steer toward the answer.
    outcome = {
        "fit_id": fit_id,
        "success": last["success"],
        "criteria": {k: details.get(k) for k in ("ok_rms", "ok_delta_bic", "ok_count", "ok_match")},
        "implication": _next_step(details),
        "submissions_left": episode.submissions_left(),
    }
    episode.append("ledger", {"kind": "submission", "rationale": rationale, **outcome})
    return json.dumps(outcome)


@mcp.tool()
def observe_or_conclude(fit_ids: List[str]) -> str:
    """Numerically decide whether to conclude or add one simulated observation.

    Pass reviewed competing fit IDs after an analysis round. Evidence is sufficient
    only when the best fit clears fixed RMS, BIC, residual-signal, detection-strength,
    fit-quality, review, and model-separation thresholds. Otherwise the tool observes
    at the feasible future time where the fitted models disagree most. Simulation is
    available only for synthetic tasks; this tool never exposes simulator truth.
    """
    fits = [_load_fit(fid) for fid in fit_ids]
    if len(fit_ids) < 2 or any(f is None for f in fits):
        return "Pass at least two valid competing fit IDs from the current analysis round."
    ranked = sorted(fits, key=lambda f: f["bic"])
    best, second = ranked[:2]
    residual_pg = rv.periodogram(data, resid=np.asarray(best["residuals"]), top_k=1)
    residual_fap = residual_pg["peaks"][0]["fap"] if residual_pg["peaks"] else 1.0
    verdicts = [r for r in episode.read("ledger") if r.get("kind") == "verdict" and r.get("fit_id") == best["id"]]
    approved = bool(verdicts and verdicts[-1].get("verdict") == "approve")
    min_strength = min((p["K_over_sigma_sqrtN"] for p in best["planets"]), default=0.0)
    bic_margin = float(second["bic"] - best["bic"])
    criteria = {
        "review_approved": approved,
        "rms_ok": bool(best["rms_ok"]),
        "delta_bic_vs_null_gte_10": bool(best["delta_bic_vs_null"] >= 10.0),
        "bic_margin_vs_runner_up_gte_10": bool(bic_margin >= 10.0),
        "residual_fap_gte_1e_3": bool(residual_fap >= 1e-3),
        "all_planet_strengths_gte_5": bool(best["planets"] and min_strength >= 5.0),
        "no_fit_flags": not best["flags"],
    }
    evidence = {
        "best_fit_id": best["id"],
        "runner_up_fit_id": second["id"],
        "bic_margin": bic_margin,
        "rms_ms": best["rms_ms"],
        "rms_limit_ms": best["rms_limit_ms"],
        "residual_peak_fap": residual_fap,
        "minimum_detection_strength": min_strength,
        "criteria": criteria,
    }
    if all(criteria.values()):
        result = {"status": "conclude", "fit": _fit_view(best), "evidence": evidence,
                  "uncertainty": "Uncertainty is bounded by the runner-up BIC margin and the residual-periodogram threshold."}
        episode.append("ledger", {"kind": "decision", **result})
        return json.dumps(result)

    rounds = len(episode.read("observe_decisions"))
    observations = len(episode.read("observations"))
    max_rounds = int(os.environ.get("STARGAZER_MAX_COMPUTE_ROUNDS", "4"))
    max_observations = int(os.environ.get("STARGAZER_MAX_OBSERVATIONS", "3"))
    if rounds >= max_rounds or observations >= max_observations or episode.time_left() <= 0:
        result = {"status": "unresolved", "evidence": evidence,
                  "reason": "Observation or compute limit reached before the numerical criteria were satisfied."}
        episode.append("ledger", {"kind": "decision", **result})
        return json.dumps(result)
    if episode.task_id.startswith("real_"):
        result = {"status": "unresolved", "evidence": evidence,
                  "reason": "Simulated observing and real telescope control are disabled for real-data tasks."}
        episode.append("ledger", {"kind": "decision", **result})
        return json.dumps(result)

    unique_times = np.unique(data.t)
    cadence = float(np.median(np.diff(unique_times))) if len(unique_times) > 1 else 1.0
    horizon = max(30.0 * max(cadence, 0.1), 0.25 * data.span)
    candidates = np.linspace(float(data.t.max() + max(cadence, 0.1)), float(data.t.max() + horizon), 128)
    predictions = np.stack([_fit_model(f, candidates) for f in ranked])
    disagreement = np.max(predictions, axis=0) - np.min(predictions, axis=0)
    chosen = int(np.argmax(disagreement))
    sigma = float(np.median(data.s))
    labels, counts = np.unique(data.inst, return_counts=True)
    row = episode.simulate_observation(float(candidates[chosen]), sigma, str(labels[np.argmax(counts)]))
    episode.append("observe_decisions", {"fit_ids": fit_ids, "time_days": row["time_days"], "evidence": evidence})
    _refresh_data()
    result = {
        "status": "observe",
        "observation": row,
        "expected_model_separation_ms": float(disagreement[chosen]),
        "observations_used": observations + 1,
        "observations_left": max_observations - observations - 1,
        "compute_rounds_left": max_rounds - rounds - 1,
        "evidence": evidence,
        "next": "Repeat the existing analyst, hypothesis, investigator, and critic cycle on the updated data.",
    }
    episode.append("ledger", {"kind": "decision", **result})
    return json.dumps(result)


repl_globals: Dict[str, Any] = {
    "np": np,
    "times_days": data.t,
    "rvs_ms": data.y,
    "sigmas_ms": data.s,
    "instruments": data.inst,
    "star_mass_sun": data.star_mass_sun,
    "fit_residuals": lambda fit_id: np.asarray(_load_fit(fit_id)["residuals"]),
}


@mcp.tool()
def PythonREPL(input_code: str) -> str:
    """A Python REPL for checks the other tools do not cover. Print to see values.

    Pre-loaded: np, times_days, rvs_ms, sigmas_ms, instruments, star_mass_sun,
    fit_residuals(fit_id). numpy and scipy are importable. No plotting.
    """
    if any(term in input_code for term in FORBIDDEN):
        out = "Code rejected: it references benchmark internals. Use only the pre-loaded data."
    else:
        if not isinstance(sys.stdout, _ThreadLocalStdoutProxy):
            sys.stdout = _ThreadLocalStdoutProxy(sys.stdout)
        out = execute_python_repl(input_code, repl_globals, repl_globals)
    episode.append("repl", {"code": input_code, "output": out})
    return out


if __name__ == "__main__":
    mcp.run()
