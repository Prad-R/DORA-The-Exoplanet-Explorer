"""Two no-LLM reference points on every Stargazer task.

oracle:  the fitter is GIVEN the true number of planets and periods within 2%,
         and returns the maximum-likelihood orbits. If this fails, no agent that
         submits a best-fitting model can pass: the data do not pin down the truth.
greedy:  periodogram -> fit -> residual periodogram, adding a planet while the
         residual peak has FAP < 1e-3 and BIC improves by > 10. One submission.

    python experiments/oracle.py            # writes experiments/oracle.json
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lab import rv  # noqa: E402
from lab.episode import BANKS, Episode  # noqa: E402

from stargazer.utils_units import semi_amplitude_ms  # noqa: E402


def _evaluate(ep: Episode, fit: dict) -> dict:
    if not fit["planets"]:
        return {"success": False, "ok_rms": False, "ok_delta_bic": False, "ok_match": False, "ok_count": False}
    ep.submit(rv.submission_payload(fit))
    sub = ep.read("submissions")[-1]
    d = sub["success_details"]
    return {"success": sub["success"], **{k: bool(d.get(k)) for k in ("ok_rms", "ok_delta_bic", "ok_match", "ok_count")},
            "match_score": d.get("match_score")}


def run(task_id: str) -> dict:
    ep = Episode(task_id, Path(tempfile.mkdtemp()))
    d = rv.Data(ep.times, ep.rvs, ep.sigmas, np.asarray(ep.instruments), ep.star_mass_sun)
    truth = ep.task.config.planets
    sigma = float(np.median(d.s))

    truth_planets = [
        {"P_days": p.P_days, "K_ms": semi_amplitude_ms(p.m_sin_i_mjup, p.P_days, p.e, d.star_mass_sun),
         "e": p.e, "omega_rad": p.omega_rad, "M0_rad": (p.l_rad - p.omega_rad) % (2 * np.pi)}
        for p in truth
    ]
    truth_stats = rv._stats(d, np.sum([rv.planet_rv(d.t, d.t[0], p) for p in truth_planets], axis=0), len(truth))

    oracle_fit = rv.fit_keplerians(d, [p.P_days * 1.02 for p in truth])
    oracle = _evaluate(ep, oracle_fit)

    # greedy pipeline, blind to the truth
    ep2 = Episode(task_id, Path(tempfile.mkdtemp()))
    periods, fit = [], rv.fit_keplerians(d, [])
    while len(periods) < ep2.max_planets:
        peak = rv.periodogram(d, resid=np.asarray(fit["residuals"]), top_k=1)["peaks"]
        if not peak or peak[0]["fap"] > 1e-3:
            break
        trial = rv.fit_keplerians(d, [p["P_days"] for p in fit["planets"]] + [peak[0]["period_days"]])
        if fit["bic"] - trial["bic"] < 10:
            break
        fit, periods = trial, [p["P_days"] for p in trial["planets"]]
    greedy = _evaluate(ep2, fit)

    k = [p["K_ms"] for p in truth_planets]
    return {
        "task_id": task_id,
        "tier": "real" if task_id.startswith("real_") else ep.tier,
        "difficulty": ep.task.truth_difficulty,
        "n_planets": len(truth),
        "n_obs": len(d.t),
        "min_K_over_sigma": min(k) / sigma,
        # detection strength of the weakest planet: K / sigma * sqrt(N / 2)
        "min_snr": min(k) / sigma * np.sqrt(len(d.t) / 2),
        "truth_rms_over_sigma": truth_stats["rms_ms"] / sigma,
        "truth_passes_rms": bool(truth_stats["rms_ms"] <= 1.5 * sigma),
        "oracle_bic_minus_truth_bic": oracle_fit["bic"] - truth_stats["bic"],
        "oracle": oracle,
        "greedy": {**greedy, "n_found": fit["n_planets"]},
    }


if __name__ == "__main__":
    tasks = sorted(f[:-5] for bank in BANKS.values() for f in os.listdir(bank) if f.endswith(".json") and f[0] in "sr")
    with Pool(4) as pool:
        results = []
        for r in pool.imap_unordered(run, tasks):
            results.append(r)
            print(f"{len(results):3d}/{len(tasks)} {r['task_id']:<18} oracle={r['oracle']['success']!s:<5} greedy={r['greedy']['success']}", flush=True)
    out = Path(__file__).parent / "oracle.json"
    out.write_text(json.dumps(sorted(results, key=lambda r: r["task_id"]), indent=1, default=float))
    for tier in ("easy", "medium", "hard", "real"):
        rs = [r for r in results if r["tier"] == tier]
        print(tier, len(rs), "oracle", sum(r["oracle"]["success"] for r in rs), "greedy", sum(r["greedy"]["success"] for r in rs),
              "oracle fits better than truth", sum(r["oracle_bic_minus_truth_bic"] <= 0 for r in rs))
