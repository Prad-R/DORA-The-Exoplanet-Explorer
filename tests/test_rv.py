"""The fitter's conventions must agree with Stargazer's forward model and evaluator."""
import time

import numpy as np
import pytest

from lab.episode import Episode
from lab.rv import Data, fit_keplerians, periodogram, submission_payload

from stargazer.config import PlanetParams
from stargazer.forward_keplerian import simulate_rv_keplerian


def _data(ep):
    return Data(ep.times, ep.rvs, ep.sigmas, np.asarray(ep.instruments), ep.star_mass_sun)


@pytest.mark.parametrize("task_id", ["seed96_diff3", "seed196_diff10"])
def test_fit_from_perturbed_truth_passes_evaluator(tmp_path, task_id):
    ep = Episode(task_id, tmp_path)
    d = _data(ep)
    start = [p.P_days * 1.02 for p in ep.task.config.planets]
    t0 = time.time()
    fit = fit_keplerians(d, start)
    elapsed = time.time() - t0

    # Stargazer's forward model reproduces the fitter's residual RMS.
    planets = [PlanetParams(inc_rad=0.0, Omega_rad=0.0, m_true_mjup=None, **p)
               for p in submission_payload(fit)["planets"]]
    rv = simulate_rv_keplerian(planets, d.t, d.star_mass_sun)
    resid = d.y - rv
    resid -= np.sum(resid / d.s**2) / np.sum(1 / d.s**2)
    assert np.sqrt(np.mean(resid**2)) == pytest.approx(fit["rms_ms"], rel=1e-3)

    assert elapsed < 120
    # On the hard task the best-fitting model is not the true system (one planet
    # has K below the noise), so only the medium task is expected to pass.
    if task_id == "seed96_diff3":
        ep.submit(submission_payload(fit))
        assert ep.state()["solved"], ep.read("submissions")[-1]["success_details"]


def test_periodogram_finds_dominant_signal(tmp_path):
    ep = Episode("seed96_diff3", tmp_path)
    pg = periodogram(_data(ep))
    assert pg["peaks"][0]["fap"] < 1e-3
