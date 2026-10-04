"""The lab's numerical decision rule: conclude, review, refine, or observe.

Observing is the expensive action, so it is reserved for the one situation more
data can fix: the current data cannot tell competing models apart, or cannot pin
down the leading model. Everything else (an unreviewed leader, a model that does
not fit, a fit stuck on a search bound) is answered by more analysis, not data.

Leader selection follows the usual parsimony rule for nested models: take the
model with the fewest planets that no larger model beats by a decisive BIC
margin. Adding a planet nearly always lowers BIC a little, so ranking by raw BIC
would promote noise-fitting planets.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from lab import rv

DECISIVE_BIC = 10.0  # Kass & Raftery (1995): a BIC difference above 10 is very strong evidence
RESIDUAL_FAP = 1e-3  # a residual peak below this false-alarm probability is an unexplained signal
MIN_STRENGTH = 5.0  # K / sigma * sqrt(N / 2): below this a planet is not a secure detection
MAX_PERIOD_OVER_BASELINE = 1.5  # beyond this the orbit is under two-thirds covered
SAME_PERIOD = 0.05  # fractional period difference below which two fits describe the same orbit

# Fit flags that mean the optimiser, not the data, is the problem.
BLOCKING_FLAGS = ("sits on its search bound", "eccentricity at the upper limit", "within 15% of each other")


def _periods(fit: Dict[str, Any]) -> List[float]:
    return sorted(p["P_days"] for p in fit["planets"])


def _same_configuration(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    pa, pb = _periods(a), _periods(b)
    return len(pa) == len(pb) and all(abs(x / y - 1.0) < SAME_PERIOD for x, y in zip(pa, pb))


def choose_leader(fits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fewest planets that no larger model beats by DECISIVE_BIC; best BIC within that count."""
    for n in sorted({f["n_planets"] for f in fits}):
        best = min((f for f in fits if f["n_planets"] == n), key=lambda f: f["bic"])
        if not any(f["n_planets"] > n and f["bic"] <= best["bic"] - DECISIVE_BIC for f in fits):
            return best
    return min(fits, key=lambda f: f["bic"])


def _check(name: str, passed: bool, text: str) -> Dict[str, Any]:
    return {"name": name, "passed": bool(passed), "explanation": text}


def assess(data: rv.Data, fits: List[Dict[str, Any]], verdict: Optional[str],
           refuted: Optional[List[List[float]]] = None) -> Dict[str, Any]:
    """Evaluate the leader of ``fits`` (all fitted on ``data``).

    ``verdict`` is the critic's latest verdict on the leader ('approve', 'reject' or None).
    ``refuted`` lists the period sets of submissions the evaluator failed.
    Returns the leader, its rivals, and the checks grouped by what failing them calls for.
    """
    leader = choose_leader(fits)
    already_failed = any(_same_configuration(leader, {"planets": [{"P_days": p} for p in ps]})
                         for ps in refuted or [])
    others = [f for f in fits if f is not leader and not _same_configuration(f, leader)]
    simpler = [f for f in others if f["n_planets"] < leader["n_planets"]]
    larger = [f for f in others if f["n_planets"] > leader["n_planets"]]
    same_count = [f for f in others if f["n_planets"] == leader["n_planets"]]

    resid_pg = rv.periodogram(data, resid=np.asarray(leader["residuals"]), top_k=1)
    resid_peak = resid_pg["peaks"][0] if resid_pg["peaks"] else None
    resid_fap = resid_peak["fap"] if resid_peak else 1.0
    strengths = [p["K_over_sigma_sqrtN"] for p in leader["planets"]]
    weakest = min(strengths, default=0.0)
    longest = max(_periods(leader), default=0.0)
    blocking = [fl for fl in leader["flags"] if any(b in fl for b in BLOCKING_FLAGS)]

    # Rivals the data cannot yet separate from the leader.
    close_simpler = [f for f in simpler if f["bic"] - leader["bic"] < DECISIVE_BIC]
    close_same = [f for f in same_count if f["bic"] - leader["bic"] < DECISIVE_BIC]

    def ids(fs):
        return ", ".join(f["id"] for f in fs)

    analysis = [
        _check("fits_the_data", leader["rms_ok"],
               f"Scatter around the model is {leader['rms_ms']:.2f} m/s; the limit is {leader['rms_limit_ms']:.2f} m/s."),
        _check("no_leftover_signal", resid_fap >= RESIDUAL_FAP,
               "No significant periodicity is left after subtracting the model." if resid_fap >= RESIDUAL_FAP else
               f"A periodicity at {resid_peak['period_days']:.2f} d remains (false-alarm probability "
               f"{resid_fap:.1e}); a planet may be missing."),
        _check("fit_converged", not blocking,
               "The optimiser converged inside its search range." if not blocking else "; ".join(blocking)),
        _check("critic_did_not_reject", verdict != "reject",
               "The critic has not rejected this fit." if verdict != "reject" else
               "The critic rejected this fit; address its reasons before deciding."),
    ]
    data_limited = [
        _check("simpler_models_ruled_out", not close_simpler,
               f"Every model with fewer planets is worse by at least {DECISIVE_BIC:.0f} in BIC." if not close_simpler
               else f"The data cannot yet rule out the simpler model(s) {ids(close_simpler)} "
                    f"(BIC difference under {DECISIVE_BIC:.0f})."),
        _check("alternatives_ruled_out", not close_same,
               "Alternative periods with the same planet count are clearly worse." if not close_same
               else f"Alternative period set(s) {ids(close_same)} fit about as well "
                    f"(BIC difference under {DECISIVE_BIC:.0f}); an alias is possible."),
        _check("planets_detected_securely", weakest >= MIN_STRENGTH,
               f"The weakest planet's signal is {weakest:.1f}× the noise (needs at least {MIN_STRENGTH:.0f})."),
        _check("periods_covered", longest <= MAX_PERIOD_OVER_BASELINE * data.span,
               f"The longest period ({longest:.1f} d) is {longest / max(data.span, 1e-9):.2f}× the "
               f"{data.span:.1f} d observing span (allowed up to {MAX_PERIOD_OVER_BASELINE}×)."),
        # The evaluator's verdict is evidence too: if the data's preferred model was
        # already refuted, the data are misleading and only more data can say how.
        _check("not_already_refuted", not already_failed,
               "No submission of this configuration has failed." if not already_failed else
               "A submission of this configuration already failed, so the current data favour a wrong "
               "model; a signal they cannot yet show (for example a longer orbit) is likely."),
    ]
    return {
        "leader": leader,
        "larger_rejected": [f["id"] for f in larger],
        "rivals": close_simpler + close_same,
        "analysis_checks": analysis,
        "data_checks": data_limited,
        "residual_peak": resid_peak,
    }


def schedule_campaign(
    data: rv.Data,
    models: List[Dict[str, Any]],
    model_fn,
    n_points: int,
    horizon_days: float,
) -> Dict[str, Any]:
    """Pick ``n_points`` future observing times.

    Times are chosen greedily where the candidate models disagree most (in units
    of the noise), then nearby times are down-weighted so the campaign also spreads
    across the window and improves phase coverage of long periods. One point per
    night at most. ``model_fn(model, times)`` returns predicted velocities.
    """
    unique = np.unique(data.t)
    cadence = float(np.median(np.diff(unique))) if len(unique) > 1 else 1.0
    start = float(data.t.max()) + max(cadence, 0.5)
    grid = np.arange(start, start + horizon_days, 0.25)
    sigma = float(np.median(data.s))
    if len(models) >= 2:
        preds = np.stack([model_fn(m, grid) for m in models])
        separation = (preds.max(axis=0) - preds.min(axis=0)) / sigma
    else:
        separation = np.zeros_like(grid)
    # A floor keeps phase coverage valuable even where the models agree.
    score = separation + 0.5
    spread = horizon_days / max(n_points, 1)
    chosen: List[float] = []
    weight = np.ones_like(grid)
    for _ in range(min(n_points, len(grid))):
        i = int(np.argmax(score * weight))
        if weight[i] <= 0:
            break
        chosen.append(float(grid[i]))
        dist = np.abs(grid - grid[i])
        weight *= 1.0 - np.exp(-((dist / (0.5 * spread)) ** 2))
        weight[dist < 0.5] = 0.0  # one point per night
    chosen.sort()
    best_sep = float(separation[np.isin(grid, chosen)].max()) if chosen else 0.0
    return {"times_days": chosen, "window_days": [float(grid[0]), float(grid[-1])],
            "max_model_separation_sigma": best_sep}
