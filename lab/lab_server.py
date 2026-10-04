"""Lab tool server (stdio MCP) for the v1 multi-agent arm.

Every sub-agent session starts its own copy of this server, so all shared
state (hypotheses, fits, verdicts, submissions, follow-up observations) lives in
the run directory and is exposed as one research record through ``ledger``.

Configured by environment: STARGAZER_TASK, STARGAZER_RUN_DIR, and the follow-up
budget STARGAZER_MAX_OBSERVATIONS (points), STARGAZER_OBS_PER_CAMPAIGN (points
per observing campaign) and STARGAZER_MAX_COMPUTE_ROUNDS (decision rounds).
"""
from __future__ import annotations

import functools
import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np
# Load SciPy's compiled modules now, before the stdio loop starts. On Windows a
# DLL first loaded by agent code, while the MCP reader thread sits in a blocking
# read on stdin, waits for that read to finish: the tool call deadlocks.
import scipy.integrate, scipy.interpolate, scipy.linalg, scipy.optimize, scipy.signal, scipy.special, scipy.stats  # noqa: E401,F401
try:  # MCP <1.0 exposed MCPServer; current MCP uses FastMCP.
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from lab import decide, rv
from lab.episode import FORBIDDEN, from_env

from stargazer.agents.tools.python_repl_tool import _ThreadLocalStdoutProxy, execute_python_repl

mcp = MCPServer("lab")
episode = from_env()
data = rv.Data(episode.times, episode.rvs, episode.sigmas, np.asarray(episode.instruments), episode.star_mass_sun)
FITS = episode.run_dir / "fits"
FITS.mkdir(exist_ok=True)


def _budget() -> Dict[str, int]:
    return {
        "max_points": int(os.environ.get("STARGAZER_MAX_OBSERVATIONS", "30")),
        "per_campaign": int(os.environ.get("STARGAZER_OBS_PER_CAMPAIGN", "10")),
        "max_rounds": int(os.environ.get("STARGAZER_MAX_COMPUTE_ROUNDS", "4")),
    }


def _refresh_data() -> None:
    global data
    data = rv.Data(episode.times, episode.rvs, episode.sigmas, np.asarray(episode.instruments), episode.star_mass_sun)
    repl_globals.update(times_days=data.t, rvs_ms=data.y, sigmas_ms=data.s, instruments=data.inst)


def synced(fn):
    """Pick up follow-up observations another agent's server added since the last call."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        episode.reload_observations()
        if len(episode.times) != len(data.t):
            _refresh_data()
        return fn(*args, **kwargs)
    return wrapper


def _load_fit(fit_id: str) -> Optional[Dict[str, Any]]:
    path = FITS / f"{fit_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _is_current(fit: Dict[str, Any]) -> bool:
    """Whether the fit was made on the data as it stands now."""
    return fit.get("n_obs", len(fit["residuals"])) == len(data.t)


def _fit_model(fit: Dict[str, Any], times: np.ndarray) -> np.ndarray:
    return np.sum(
        [rv.planet_rv(times, data.t[0], p) for p in fit["planets"]], axis=0
    ) if fit["planets"] else np.zeros_like(times)


def _residuals(fit: Dict[str, Any]) -> np.ndarray:
    """Residuals of a fit's model on the current data (recomputed if newer data arrived)."""
    if _is_current(fit):
        return np.asarray(fit["residuals"])
    return rv._stats(data, _fit_model(fit, data.t), fit["n_planets"])["resid"]


def _fit_view(fit: Dict[str, Any]) -> Dict[str, Any]:
    """What an agent sees of a fit: everything except the residual array."""
    view = {k: v for k, v in fit.items() if k != "residuals"}
    view["planets"] = [
        {k: round(float(v), 5) for k, v in p.items() if k in ("P_days", "K_ms", "e", "omega_rad", "K_over_sigma_sqrtN")}
        for p in fit["planets"]
    ]
    return view


def _store_fit(fit: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    fid = episode.next_id("F")
    fit.update({"id": fid, "n_obs": len(data.t), **extra})
    (FITS / f"{fid}.json").write_text(json.dumps(fit))
    episode.append("ledger", {"kind": "fit", **_fit_view(fit)})
    return fit


def _refit(fit: Dict[str, Any]) -> Dict[str, Any]:
    """Refit a fit's planet configuration on the current data, starting from its periods."""
    new = rv.fit_keplerians(data, [p["P_days"] for p in fit["planets"]], period_tolerance=0.25)
    return _store_fit(new, hypothesis_id=fit.get("hypothesis_id"), period_tolerance=0.25, refit_of=fit["id"])


@mcp.tool()
@synced
def task_summary() -> str:
    """Dataset facts and what is left of the budget."""
    b = _budget()
    return json.dumps(
        {
            "n_obs": len(data.t),
            "follow_up_points_so_far": episode.n_follow_ups,
            "baseline_days": round(data.span, 2),
            "median_sigma_ms": round(float(np.median(data.s)), 3),
            "rv_range_ms": [round(float(data.y.min()), 2), round(float(data.y.max()), 2)],
            "instruments": sorted(set(episode.instruments)),
            "star_mass_sun": data.star_mass_sun,
            "pass_criteria": "RMS <= 1.5 x median sigma, model preferred over a constant by BIC, "
            "correct planet count, and orbital parameters close to the true ones",
            "submissions_left": episode.submissions_left(),
            "follow_up_points_left": max(0, b["max_points"] - episode.n_follow_ups),
            "points_per_campaign": b["per_campaign"],
            "decision_rounds_left": max(0, b["max_rounds"] - len(episode.read("rounds"))),
            "seconds_left": int(episode.time_left()),
        }
    )


@mcp.tool()
@synced
def periodogram(residuals_of_fit: Optional[str] = None, top_k: int = 6) -> str:
    """Generalised Lomb-Scargle peaks of the data, or of the residuals of a fit ID.

    Each peak carries its false-alarm probability, the peaks it is a harmonic of,
    and its sampling aliases (periods that the observing cadence makes look alike).
    Residuals of a fit made before new observations arrived are recomputed on the
    current data.
    """
    resid = None
    if residuals_of_fit:
        fit = _load_fit(residuals_of_fit)
        if fit is None:
            return f"Unknown fit id {residuals_of_fit!r}."
        resid = _residuals(fit)
    return json.dumps(rv.periodogram(data, resid=resid, top_k=top_k))


@mcp.tool()
@synced
def propose_hypothesis(periods_days: List[float], rationale: str) -> str:
    """Register a candidate planetary system (one starting period per planet; an
    empty list is the no-planet hypothesis). Returns its hypothesis ID."""
    hid = episode.next_id("H")
    episode.append("ledger", {"kind": "hypothesis", "id": hid, "periods_days": periods_days,
                              "rationale": rationale, "label": "agent-generated hypothesis"})
    return f"{hid} registered with {len(periods_days)} planet(s)."


@mcp.tool()
@synced
def fit_hypothesis(hypothesis_id: str, period_tolerance: float = 0.1) -> str:
    """Fit Keplerian orbits for a hypothesis by global optimisation and return the fit.

    Periods may move by ``period_tolerance`` (fractional) from the hypothesis's
    starting values. The result includes RMS against the pass limit, BIC, and
    flags for periods stuck on a bound, extreme eccentricity, or near-equal periods.
    """
    hyp = next((r for r in episode.read("ledger") if r["kind"] == "hypothesis" and r["id"] == hypothesis_id), None)
    if hyp is None:
        return f"Unknown hypothesis id {hypothesis_id!r}."
    tol = min(max(period_tolerance, 0.005), 0.5)
    fit = rv.fit_keplerians(data, hyp["periods_days"], period_tolerance=tol)
    return json.dumps(_fit_view(_store_fit(fit, hypothesis_id=hypothesis_id, period_tolerance=tol)))


@mcp.tool()
@synced
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
    """Add an entry to the research record. kind: 'evidence', 'plan' or 'decision'.

    Start with one plain-English sentence stating the takeaway; details follow."""
    if kind not in ("evidence", "plan", "decision"):
        return "kind must be 'evidence', 'plan' or 'decision'."
    episode.append("ledger", {"kind": kind, "text": text})
    return "Recorded."


@mcp.tool()
def ledger() -> str:
    """The shared research record: evidence, hypotheses, fits, verdicts, plans,
    decisions, observing campaigns and submission feedback, in order."""
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
@synced
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


def _decision(status: str, summary: str, **fields: Any) -> str:
    entry = {"kind": "decision", "status": status, "summary": summary, **fields}
    episode.append("ledger", entry)
    return json.dumps({k: v for k, v in entry.items() if k != "kind"})


@mcp.tool()
@synced
def observe_or_conclude(fit_ids: List[str]) -> str:
    """Decide, by fixed numerical rules, what the lab needs next. Pass every fit
    the lab considers a serious candidate (at least two, differing in planet count
    or periods).

    The leader is the model with the fewest planets that no larger model beats by
    10 or more in BIC. Then:
    - `needs_review`: the critic has not reviewed the leader. Nothing is spent.
    - `refine`: the leader does not fit, leaves a signal, did not converge, or was
      rejected. More analysis is needed, not more data.
    - `observe`: the data cannot separate the leader from a rival or cannot pin it
      down. A campaign of several follow-up points is simulated where the models
      disagree most, and every fit passed in is refitted on the enlarged data.
    - `conclude`: every check passed; submit the leader.
    - `unresolved`: more data is needed but the follow-up budget is spent.
    """
    fits = [_load_fit(fid) for fid in fit_ids]
    missing = [fid for fid, f in zip(fit_ids, fits) if f is None]
    if missing:
        return f"Unknown fit id(s): {', '.join(missing)}."
    if len(fits) < 2:
        return "Pass at least two competing fits so the decision compares hypotheses."
    stale = [f for f in fits if not _is_current(f)]
    if stale:
        refits = {f["id"]: _refit(f)["id"] for f in stale}
        return json.dumps({
            "status": "refitted",
            "summary": (f"{len(stale)} fit(s) predate the latest observations, so they were refitted on the "
                        f"current {len(data.t)} points. Have the critic review the new leader, then call "
                        "observe_or_conclude again with the new fit IDs."),
            "refits": refits,
        })

    verdicts = {r["fit_id"]: r["verdict"] for r in episode.read("ledger") if r.get("kind") == "verdict"}
    a = decide.assess(data, fits, None)
    leader = a["leader"]
    if leader["id"] not in verdicts:
        return _decision(
            "needs_review",
            f"{leader['id']} ({leader['n_planets']} planet(s)) is the leading model: no larger model beats it by "
            f"{decide.DECISIVE_BIC:.0f} or more in BIC. Ask the critic to review {leader['id']}, then decide again.",
            leader=leader["id"])
    refuted = [[p["P_days"] for p in s["payload"]["planets"]]
               for s in episode.read("submissions") if s.get("evaluated") and not s.get("success")]
    a = decide.assess(data, fits, verdicts[leader["id"]], refuted)

    b = _budget()
    checks = a["analysis_checks"] + a["data_checks"]
    evidence = {"leader": leader["id"], "n_planets": leader["n_planets"],
                "larger_models_not_needed": a["larger_rejected"], "checks": checks}
    failed_analysis = [c for c in a["analysis_checks"] if not c["passed"]]
    failed_data = [c for c in a["data_checks"] if not c["passed"]]
    if not failed_analysis and not failed_data:
        return _decision(
            "conclude",
            f"The data decide the question: {leader['id']} ({leader['n_planets']} planet(s)) fits, leaves no "
            "signal, beats every simpler model decisively, and no larger model is needed. Submit it.",
            fit=_fit_view(leader), **evidence)

    # Refining and observing each cost one decision round.
    if len(episode.read("rounds")) >= b["max_rounds"]:
        return _decision("unresolved", "The checks are not all met and the decision-round budget is spent. "
                         + " ".join(c["explanation"] for c in failed_analysis + failed_data), **evidence)
    episode.append("rounds", {"fit_ids": fit_ids})

    if failed_analysis:
        return _decision(
            "refine",
            f"{leader['id']} needs more analysis before more data would help: "
            + " ".join(c["explanation"] for c in failed_analysis),
            **evidence)

    points_left = b["max_points"] - episode.n_follow_ups
    why = " ".join(c["explanation"] for c in failed_data)
    if points_left <= 0 or episode.task_id.startswith("real_"):
        reason = ("Simulated observing is disabled for real-data tasks." if episode.task_id.startswith("real_")
                  else "The follow-up observation budget is spent.")
        return _decision("unresolved", f"More data is needed ({why}) but none can be taken. {reason}", **evidence)

    rivals = a["rivals"]
    longest = max(p["P_days"] for p in leader["planets"])
    # Long enough to cover the longest fitted orbit, but bounded so one campaign
    # cannot run for years on a period the data barely constrain.
    horizon = float(min(max(0.5 * data.span, longest, 30.0), max(2.0 * data.span, 90.0)))
    plan = decide.schedule_campaign(data, [leader] + rivals, _fit_model,
                                    min(b["per_campaign"], points_left), horizon)
    sigma = float(np.median(data.s))
    labels, counts = np.unique(data.inst, return_counts=True)
    instrument = str(labels[np.argmax(counts)])
    rows = [episode.simulate_observation(t, sigma, instrument) for t in plan["times_days"]]
    _refresh_data()
    episode.append("observe_decisions", {"fit_ids": fit_ids, "times_days": plan["times_days"], "evidence": evidence})
    refits = {f["id"]: _refit(f)["id"] for f in fits}
    timing = (f"timed where the competing models disagree most (up to {plan['max_model_separation_sigma']:.1f}× "
              "the noise) and spread to cover the longest orbit"
              if plan["max_model_separation_sigma"] >= 1.0 else
              "spread evenly to extend the time span and the phase coverage of the orbits")
    return _decision(
        "observe",
        f"The current data cannot settle the question: {why} Observed {len(rows)} new points between day "
        f"{plan['times_days'][0]:.1f} and day {plan['times_days'][-1]:.1f}, {timing}. Every fit was refitted "
        f"on the {len(data.t)} points; have the critic review the new leader, then decide again.",
        observations=rows, campaign=plan, refits=refits,
        follow_up_points_left=points_left - len(rows), **evidence)


repl_globals: Dict[str, Any] = {
    "np": np,
    "times_days": data.t,
    "rvs_ms": data.y,
    "sigmas_ms": data.s,
    "instruments": data.inst,
    "star_mass_sun": data.star_mass_sun,
    "fit_residuals": lambda fit_id: _residuals(_load_fit(fit_id)),
}


@mcp.tool()
@synced
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
