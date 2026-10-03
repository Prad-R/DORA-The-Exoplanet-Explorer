"""Deterministic radial-velocity analysis: periodograms, alias families, Keplerian fits.

Conventions follow Stargazer's forward model and evaluator so that a fit is
submission-ready without conversion by the agent:
  rv = sum_i K_i [cos(nu_i + omega_i) + e_i cos(omega_i)] + gamma_instrument
  M0 is the mean anomaly at t_ref = times[0];  l_rad = (omega + M0) mod 2pi
  per-instrument gamma is the weighted mean of the residuals (as the evaluator does)
  BIC uses k = 5 * n_planets + n_instruments
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy.optimize import differential_evolution, least_squares

TWO_PI = 2.0 * np.pi
E_MAX = 0.8  # Stargazer rejects submissions with e > 0.8


@dataclass
class Data:
    t: np.ndarray
    y: np.ndarray
    s: np.ndarray
    inst: np.ndarray  # instrument label per point
    star_mass_sun: float

    @property
    def span(self) -> float:
        return float(self.t.max() - self.t.min())

    @property
    def n_inst(self) -> int:
        return len(np.unique(self.inst))


# -- Kepler ------------------------------------------------------------------
def solve_kepler(M: np.ndarray, e: float) -> np.ndarray:
    M = np.mod(M, TWO_PI)
    if e == 0.0:
        return M
    E = M + e * np.sin(M)
    for _ in range(60):
        step = (E - e * np.sin(E) - M) / (1.0 - e * np.cos(E))
        E = E - step
        if np.max(np.abs(step)) < 1e-12:
            break
    return E


def true_anomaly(t: np.ndarray, t_ref: float, P: float, e: float, M0: float) -> np.ndarray:
    E = solve_kepler(M0 + TWO_PI * (t - t_ref) / P, e)
    return 2.0 * np.arctan2(np.sqrt(1.0 + e) * np.sin(E / 2.0), np.sqrt(1.0 - e) * np.cos(E / 2.0))


def planet_rv(t: np.ndarray, t_ref: float, p: Dict[str, float]) -> np.ndarray:
    nu = true_anomaly(t, t_ref, p["P_days"], p["e"], p["M0_rad"])
    return p["K_ms"] * (np.cos(nu + p["omega_rad"]) + p["e"] * np.cos(p["omega_rad"]))


def msini_mjup(K: float, P: float, e: float, star_mass_sun: float) -> float:
    """Invert Stargazer's semi_amplitude_ms."""
    return float(
        K * np.sqrt(1.0 - e * e) / (28.4329 * star_mass_sun ** (-2.0 / 3.0) * (P / 365.25) ** (-1.0 / 3.0))
    )


# -- offsets and statistics --------------------------------------------------
def _offsets(d: Data, resid: np.ndarray) -> np.ndarray:
    """Per-instrument weighted-mean offset, as a per-point array."""
    out = np.zeros_like(resid)
    w = 1.0 / d.s**2
    for label in np.unique(d.inst):
        m = d.inst == label
        out[m] = np.sum(w[m] * resid[m]) / np.sum(w[m])
    return out


def _stats(d: Data, model_planets: np.ndarray, n_planets: int) -> Dict[str, float]:
    gamma = _offsets(d, d.y - model_planets)
    resid = d.y - model_planets - gamma
    n = len(d.y)
    ll = -0.5 * np.sum(resid**2 / d.s**2 + np.log(TWO_PI * d.s**2))
    bic = -2.0 * ll + (5 * n_planets + d.n_inst) * np.log(n)
    return {
        "rms_ms": float(np.sqrt(np.mean(resid**2))),
        "chi2_red": float(np.sum(resid**2 / d.s**2) / max(1, n - 5 * n_planets - d.n_inst)),
        "bic": float(bic),
        "resid": resid,
        "gamma": gamma,
    }


def null_bic(d: Data) -> float:
    return _stats(d, np.zeros_like(d.y), 0)["bic"]


# -- periodogram -------------------------------------------------------------
def gls(t: np.ndarray, y: np.ndarray, s: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    """Generalised Lomb-Scargle power (floating mean), Zechmeister & Kuerster 2009."""
    w = 1.0 / s**2
    w = w / w.sum()
    y0 = y - np.sum(w * y)
    YY = np.sum(w * y0**2)
    arg = TWO_PI * np.outer(freqs, t)
    c, sn = np.cos(arg), np.sin(arg)
    C, S = c @ w, sn @ w
    YC, YS = c @ (w * y0), sn @ (w * y0)
    CC = (c * c) @ w - C * C
    SS = (sn * sn) @ w - S * S
    CS = (c * sn) @ w - C * S
    D = CC * SS - CS**2
    D = np.where(np.abs(D) < 1e-300, 1e-300, D)
    return (SS * YC**2 + CC * YS**2 - 2.0 * CS * YC * YS) / (YY * D)


def _grid(d: Data, p_min: float, p_max: float, oversample: float = 8.0) -> np.ndarray:
    df = 1.0 / (oversample * max(d.span, 1.0))
    return np.arange(1.0 / p_max, 1.0 / p_min, df)


def _peaks(freqs: np.ndarray, power: np.ndarray, k: int) -> List[int]:
    idx = np.where((power[1:-1] > power[:-2]) & (power[1:-1] >= power[2:]))[0] + 1
    return list(idx[np.argsort(power[idx])[::-1][:k]])


def window_peaks(d: Data, freqs: np.ndarray, k: int = 3) -> List[Dict[str, float]]:
    """Strongest sampling-window frequencies; each one spawns aliases f +- f_w."""
    arg = TWO_PI * np.outer(freqs, d.t)
    win = (np.cos(arg).sum(axis=1) ** 2 + np.sin(arg).sum(axis=1) ** 2) / len(d.t) ** 2
    lo = freqs > 2.0 / max(d.span, 1.0)  # skip the lobe around zero frequency
    f, p = freqs[lo], win[lo]
    return [
        {"period_days": float(1.0 / f[i]), "strength": float(p[i])}
        for i in _peaks(f, p, k)
        if p[i] > 0.3
    ]


def periodogram(
    d: Data,
    resid: Optional[np.ndarray] = None,
    p_min: float = 1.1,
    p_max: Optional[float] = None,
    top_k: int = 6,
) -> Dict[str, Any]:
    """Top periodogram peaks of the data (or of fit residuals) with false-alarm
    probabilities, harmonic relations and sampling aliases."""
    y = resid if resid is not None else d.y - _offsets(d, d.y)
    p_max = p_max or 3.0 * d.span
    freqs = _grid(d, p_min, p_max)
    power = gls(d.t, y, d.s, freqs)
    n = len(d.t)
    m_indep = max(1.0, d.span * (freqs[-1] - freqs[0]))
    wins = window_peaks(d, _grid(d, 0.9, d.span))
    peaks = []
    for i in _peaks(freqs, power, top_k):
        p0 = float(min(power[i], 1.0 - 1e-12))
        prob = (1.0 - p0) ** ((n - 3) / 2.0)
        fap = float(1.0 - (1.0 - prob) ** m_indep) if prob > 1e-12 else float(m_indep * prob)
        f = freqs[i]
        aliases = sorted(
            {
                round(1.0 / abs(f + sign * 1.0 / w["period_days"]), 3)
                for w in wins
                for sign in (-1.0, 1.0)
                if abs(f + sign * 1.0 / w["period_days"]) > 1.0 / (10.0 * d.span)
            }
        )
        peaks.append(
            {
                "period_days": float(1.0 / f),
                "power": p0,
                "fap": fap,
                "longer_than_baseline": bool(1.0 / f > d.span),
                "alias_periods_days": aliases,
            }
        )
    for a in peaks:
        a["harmonic_of"] = [
            round(b["period_days"], 3)
            for b in peaks
            if b is not a
            and any(abs(a["period_days"] / b["period_days"] - r) < 0.04 * r for r in (0.5, 2.0, 1 / 3, 3.0))
        ]
    return {
        "baseline_days": d.span,
        "n_obs": n,
        "window_function_peaks": wins,
        "peaks": peaks,
    }


# -- fitting -----------------------------------------------------------------
def _basis(d: Data, P: float, e: float, M0: float) -> np.ndarray:
    """rv = A (cos nu + e) - B sin nu, with A = K cos(omega), B = K sin(omega)."""
    nu = true_anomaly(d.t, d.t[0], P, e, M0)
    return np.stack([np.cos(nu) + e, -np.sin(nu)], axis=1)


def _linear_solve(d: Data, nonlin: np.ndarray) -> tuple:
    """Given (P, e, M0) per planet, solve amplitudes and instrument offsets exactly."""
    n_pl = len(nonlin) // 3
    labels = np.unique(d.inst)
    cols = [_basis(d, *nonlin[3 * i : 3 * i + 3]) for i in range(n_pl)]
    cols.append(np.stack([(d.inst == lab).astype(float) for lab in labels], axis=1))
    X = np.concatenate(cols, axis=1) / d.s[:, None]
    coef, *_ = np.linalg.lstsq(X, d.y / d.s, rcond=None)
    chi2 = float(np.sum((X @ coef - d.y / d.s) ** 2))
    return coef, chi2


def _planets_from(d: Data, nonlin: np.ndarray, coef: np.ndarray) -> List[Dict[str, float]]:
    planets = []
    for i in range(len(nonlin) // 3):
        P, e, M0 = nonlin[3 * i : 3 * i + 3]
        A, B = coef[2 * i : 2 * i + 2]
        omega = float(np.arctan2(B, A) % TWO_PI)
        planets.append(
            {
                "P_days": float(P),
                "K_ms": float(np.hypot(A, B)),
                "e": float(e),
                "omega_rad": omega,
                "M0_rad": float(M0 % TWO_PI),
            }
        )
    return planets


def _e_penalty(e: np.ndarray) -> np.ndarray:
    """-2 ln of the Kipping (2013) Beta(0.867, 3.03) eccentricity prior, shifted to be >= 0."""
    e = np.clip(e, 1e-3, 0.999)
    return 0.266 * (np.log(e) - np.log(1e-3)) - 4.06 * np.log(1.0 - e)


def fit_keplerians(
    d: Data,
    periods: Sequence[float],
    period_tolerance: float = 0.1,
    max_e: float = E_MAX,
    seed: int = 0,
    e_prior: bool = False,
) -> Dict[str, Any]:
    """Jointly fit one Keplerian per entry of ``periods``.

    Global search (differential evolution) over period, eccentricity and phase
    of every planet, with amplitudes and instrument offsets solved exactly at
    each step, followed by a local polish. Periods may move by
    ``period_tolerance`` (fractional) around their starting values.
    """
    periods = [float(p) for p in periods]
    n_pl = len(periods)
    if n_pl == 0:
        st = _stats(d, np.zeros_like(d.y), 0)
        return _report(d, [], st, [])
    bounds, lo, hi = [], [], []
    for p in periods:
        b = [(p * (1 - period_tolerance), p * (1 + period_tolerance)), (0.0, max_e), (0.0, TWO_PI)]
        bounds += b
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    def cost(x: np.ndarray) -> float:
        chi2 = _linear_solve(d, x)[1]
        return chi2 + float(np.sum(_e_penalty(x[1::3]))) if e_prior else chi2

    x0 = np.array([v for p in periods for v in (p, 0.05, np.pi)])
    de = differential_evolution(
        cost, bounds, seed=seed, tol=1e-8, popsize=20, maxiter=400 // max(1, n_pl) + 150,
        init="sobol", x0=x0, polish=False, updating="deferred",
    )

    def resid(x: np.ndarray) -> np.ndarray:
        coef, _ = _linear_solve(d, x)
        cols = [_basis(d, *x[3 * i : 3 * i + 3]) @ coef[2 * i : 2 * i + 2] for i in range(n_pl)]
        r = (np.sum(cols, axis=0) + _inst_term(d, coef[2 * n_pl :]) - d.y) / d.s
        return np.concatenate([r, np.sqrt(_e_penalty(x[1::3]))]) if e_prior else r

    # Phase is periodic; widen its bounds for the polish so it cannot stick at 0 or 2pi.
    lo_p, hi_p = lo.copy(), hi.copy()
    lo_p[2::3], hi_p[2::3] = -TWO_PI, 2 * TWO_PI
    polished = least_squares(resid, np.clip(de.x, lo_p, hi_p), bounds=(lo_p, hi_p), x_scale="jac")
    x = polished.x if polished.cost * 2 <= de.fun else de.x

    coef, _ = _linear_solve(d, x)
    planets = _planets_from(d, x, coef)
    model = np.sum([planet_rv(d.t, d.t[0], p) for p in planets], axis=0)
    flags = []
    for i, p in enumerate(planets):
        p_lo, p_hi = bounds[3 * i]
        if p["P_days"] <= p_lo * 1.002 or p["P_days"] >= p_hi * 0.998:
            flags.append(f"planet {i + 1}: period {p['P_days']:.3f} d sits on its search bound; widen period_tolerance or change the starting period")
        if p["e"] >= max_e - 0.01:
            flags.append(f"planet {i + 1}: eccentricity at the upper limit {max_e}; often a sign of a missing planet or a wrong period")
        if p["P_days"] > d.span:
            flags.append(f"planet {i + 1}: period exceeds the {d.span:.1f} d baseline; poorly constrained")
    return _report(d, planets, _stats(d, model, n_pl), flags)


def _inst_term(d: Data, gammas: np.ndarray) -> np.ndarray:
    out = np.zeros_like(d.y)
    for g, lab in zip(gammas, np.unique(d.inst)):
        out[d.inst == lab] = g
    return out


def _report(d: Data, planets: List[Dict[str, float]], st: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
    sigma_med = float(np.median(d.s))
    n = len(d.y)
    for p in planets:
        p["m_sin_i_mjup"] = msini_mjup(p["K_ms"], p["P_days"], p["e"], d.star_mass_sun)
        p["l_rad"] = float((p["omega_rad"] + p["M0_rad"]) % TWO_PI)
        # Detection strength of this planet given the white-noise level.
        p["K_over_sigma_sqrtN"] = float(p["K_ms"] / sigma_med * np.sqrt(n / 2.0))
    for i, a in enumerate(planets):
        for b in planets[i + 1 :]:
            ratio = max(a["P_days"], b["P_days"]) / min(a["P_days"], b["P_days"])
            if ratio < 1.15:
                flags.append(f"periods {a['P_days']:.2f} d and {b['P_days']:.2f} d are within 15% of each other; unlikely to be two stable planets")
    rms_limit = 1.5 * sigma_med
    return {
        "n_planets": len(planets),
        "planets": planets,
        "rms_ms": st["rms_ms"],
        "rms_limit_ms": rms_limit,
        "rms_ok": bool(st["rms_ms"] <= rms_limit),
        "chi2_red": st["chi2_red"],
        "bic": st["bic"],
        "delta_bic_vs_null": float(null_bic(d) - st["bic"]),
        "flags": flags,
        "residuals": st["resid"].tolist(),
    }


def submission_payload(fit: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("P_days", "m_sin_i_mjup", "e", "omega_rad", "l_rad")
    return {"planets": [{k: float(p[k]) for k in keys} for p in fit["planets"]]}
