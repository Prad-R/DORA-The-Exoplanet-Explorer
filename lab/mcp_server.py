"""Stargazer tool server (stdio MCP) for Omnigent agents.

Configured by environment: STARGAZER_TASK, STARGAZER_RUN_DIR.
Exposes the same two tools as Stargazer's reference agent, backed by Stargazer's
own implementations, so the plain arm matches the paper's interface.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

import numpy as np
try:  # MCP <1.0 exposed MCPServer; current MCP uses FastMCP.
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError:
    from mcp.server.fastmcp import FastMCP as MCPServer

from lab.episode import FORBIDDEN, from_env

from stargazer.agents.tools.python_repl_tool import _ThreadLocalStdoutProxy, execute_python_repl
from stargazer.benchmarks import baselines

GUIDE = (
    "Stargazer Submission Guide\n"
    "1) Preferred fields: P_days, m_sin_i_mjup, e, omega_rad, l_rad\n"
    "2) Reference epoch: t_ref = times_days[0]\n"
    "3) Convert M0 to l_rad via l_rad = (Omega_rad + omega_rad + M0) mod 2pi\n"
    "4) Avoid mixing phase aliases; if using l_rad, treat it as canonical\n"
    "5) Before submit: verify converted action rv_model residual RMS is near sigma\n"
)

mcp = MCPServer("stargazer")
episode = from_env()
history: List[Dict[str, Any]] = []


def stargazer_planet_from_fit(
    P_days: float,
    K_ms: float,
    e: float,
    omega_rad: float,
    M0_rad: float,
    m_sin_i_mjup: Optional[float] = None,
    inc_rad: float = np.pi / 2.0,
    Omega_rad: float = 0.0,
) -> Dict[str, float]:
    """Convert fitted Keplerian params into canonical Stargazer planet fields."""
    # Mirrors the helper defined inside TabularRvAgent.run().
    P_days_f = float(P_days)
    K_ms_f = float(max(0.0, K_ms))
    e_f = float(np.clip(e, 0.0, 0.8))
    omega_f = float(omega_rad % (2.0 * np.pi))
    M0_f = float(M0_rad % (2.0 * np.pi))
    Omega_f = float(Omega_rad % (2.0 * np.pi))
    if m_sin_i_mjup is None:
        denom = (
            28.4329
            * (episode.star_mass_sun ** (-2.0 / 3.0))
            * ((P_days_f / 365.25) ** (-1.0 / 3.0))
            / np.sqrt(max(1e-12, 1.0 - e_f * e_f))
        )
        msi = float(np.clip(K_ms_f / denom, 1e-3, 30.0))
    else:
        msi = float(np.clip(m_sin_i_mjup, 1e-3, 30.0))
    return {
        "P_days": P_days_f,
        "m_sin_i_mjup": msi,
        "e": e_f,
        "inc_rad": float(np.clip(inc_rad, 0.0, np.pi)),
        "Omega_rad": Omega_f,
        "omega_rad": omega_f,
        "l_rad": float((Omega_f + omega_f + M0_f) % (2.0 * np.pi)),
    }


repl_globals: Dict[str, Any] = {
    "np": np,
    "times_days": episode.times,
    "rvs_ms": episode.rvs,
    "sigmas_ms": episode.sigmas,
    "instruments": episode.instruments,
    "baselines": baselines,
    "history": history,
    "star_mass_sun": episode.star_mass_sun,
    "t_ref_days": float(episode.times[0]),
    "stargazer_planet_from_fit": stargazer_planet_from_fit,
    "STARGAZER_SUBMISSION_GUIDE": GUIDE,
    "_protocol_guide_ack": False,
}


@mcp.tool()
def PythonREPL(input_code: str) -> str:
    """A Python REPL with persistent state. Print values to see them. No plotting.

    Pre-loaded names (do not import them): np, times_days, rvs_ms, sigmas_ms,
    instruments, baselines, history, star_mass_sun, t_ref_days,
    stargazer_planet_from_fit, STARGAZER_SUBMISSION_GUIDE. numpy and scipy are importable.
    """
    if any(term in input_code for term in FORBIDDEN):
        out = "Code rejected: it references benchmark internals. Use only the pre-loaded data."
    else:
        # Stargazer captures prints through a sys.stdout proxy; stdout is also the
        # MCP channel, so make sure the proxy is in place before running code.
        if not isinstance(sys.stdout, _ThreadLocalStdoutProxy):
            sys.stdout = _ThreadLocalStdoutProxy(sys.stdout)
        out = execute_python_repl(input_code, repl_globals, repl_globals)
    episode.append("repl", {"code": input_code, "output": out})
    return out


@mcp.tool()
def submit_action(
    planets: List[Dict[str, float]],
    rv_offset_ms: Optional[float] = None,
    noise_jitter_ms: Optional[float] = None,
    notes: Optional[str] = None,
) -> str:
    """Submit a candidate planetary system for evaluation; returns per-criterion feedback.

    Each planet uses Stargazer-native fields: P_days (> 0.5), m_sin_i_mjup, e (0-0.8),
    omega_rad, l_rad (mean longitude at t_ref = times_days[0]). Submissions are limited.
    """
    if not repl_globals.get("_protocol_guide_ack", False):
        return (
            "Submission blocked: protocol guide not acknowledged yet. "
            "Run PythonREPL to read `STARGAZER_SUBMISSION_GUIDE`, then set "
            "`_protocol_guide_ack = True` before calling submit_action."
        )
    payload: Dict[str, Any] = {"planets": planets}
    if rv_offset_ms is not None:
        payload["rv_offset_ms"] = rv_offset_ms
    if noise_jitter_ms is not None:
        payload["noise_jitter_ms"] = noise_jitter_ms
    if notes:
        payload["notes"] = notes
    result = episode.submit(payload)
    history.append({"step": len(history) + 1, "planets": planets, "result": result[:2000]})
    return result


if __name__ == "__main__":
    mcp.run()
