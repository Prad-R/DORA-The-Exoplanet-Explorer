"""Per-task brief: Stargazer's own system prompt, sent as the first message."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from lab.episode import Episode

from stargazer.agents.tabular_agent import TabularRvAgent

# Tool-call caps per tier; Stargazer's CLI default is 20 and its Hard-tier case
# study ran 40 steps.
MAX_TOOL_CALLS = {"easy": 20, "medium": 30, "hard": 40}
# The lab's PI spends most calls on orchestration (two per dispatch: send, then
# read the reply), so it gets a larger cap than the single-agent baseline.
# Report this difference when comparing the arms.
LAB_MAX_TOOL_CALLS = {"easy": 40, "medium": 60, "hard": 80}


def task_brief(episode: Episode) -> str:
    stub = SimpleNamespace(
        _current_obs=episode.obs,
        config=SimpleNamespace(
            max_tool_calls=MAX_TOOL_CALLS[episode.tier],
            max_execution_time=float(episode.budget["max_time"]),
            max_planets=episode.max_planets,
        ),
        env=SimpleNamespace(
            submission_mode=episode.env.submission_mode,
            max_steps=episode.budget["max_submissions"],
        ),
    )
    return TabularRvAgent._build_system_prompt(stub).strip()


def lab_brief(episode: Episode, max_points: int, per_campaign: int, max_rounds: int) -> str:
    """First message for the v1 lab: the question and the budget, no method."""
    s = episode
    observing = (f"- Follow-up observing: up to {max_points} simulated points, taken in campaigns of up to "
                 f"{per_campaign}, only when the decision tool says the data cannot settle the question\n"
                 if not s.task_id.startswith("real_") else "- Follow-up observing: not available for real data\n")
    return (
        "New target. Find the planets orbiting this star from its radial-velocity data.\n\n"
        f"- Observations: {len(s.times)} over {s.times[-1] - s.times[0]:.1f} days, "
        f"{len(set(s.instruments))} instrument(s)\n"
        f"- Median uncertainty: {float(np.median(s.sigmas)):.2f} m/s\n"
        f"- Budget: {s.budget['max_submissions']} submissions, {s.budget['max_time']} seconds, "
        f"{max_rounds} decision rounds, at most {s.max_planets} planets\n"
        + observing +
        "\nRun the discovery loop and report."
    )
