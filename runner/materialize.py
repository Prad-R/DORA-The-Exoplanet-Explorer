"""Fill an agent template for one task and write it into the run directory."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lab.brief import MAX_TOOL_CALLS, lab_brief, task_brief  # noqa: E402
from lab.episode import Episode  # noqa: E402


def _venv_python() -> Path:
    windows = REPO / ".venv" / "Scripts" / "python.exe"
    posix = REPO / ".venv" / "bin" / "python"
    return windows if windows.exists() else posix if posix.exists() else Path(sys.executable)


def materialize(arm: str, task_id: str, run_dir: Path, human_gate: bool = False,
                max_observations: int = 3, max_compute_rounds: int = 4,
                research_prompt: str = "") -> tuple[Path, str]:
    """Return (agent directory, first message) for ``arm`` on ``task_id``."""
    run_dir = Path(run_dir).resolve()
    episode = Episode(task_id, run_dir / "state")
    agent_dir = run_dir / "agent"
    if agent_dir.exists():
        shutil.rmtree(agent_dir)
    shutil.copytree(REPO / "agents" / arm, agent_dir)
    values = {
        "PYTHON": str(_venv_python()),
        "REPO": str(REPO),
        "TASK": task_id,
        "RUN_DIR": str(run_dir / "state"),
        "MAX_TIME": str(episode.budget["max_time"]),
        "MAX_TOOL_CALLS": str(MAX_TOOL_CALLS[episode.tier]),
        "MAX_SUBMISSIONS": str(episode.budget["max_submissions"]),
        "HUMAN_GATE": "true" if human_gate else "false",
        "MAX_OBSERVATIONS": str(max_observations),
        "MAX_COMPUTE_ROUNDS": str(max_compute_rounds),
    }
    for path in agent_dir.rglob("*"):
        if path.suffix in {".yaml", ".md"}:
            text = path.read_text()
            for key, value in values.items():
                text = text.replace("{{" + key + "}}", value)
            path.write_text(text)
    budget = {**episode.budget, "tier": episode.tier, "difficulty": episode.task.truth_difficulty,
              "max_tool_calls": MAX_TOOL_CALLS[episode.tier], "max_observations": max_observations,
              "max_compute_rounds": max_compute_rounds}
    (run_dir / "budget.json").write_text(json.dumps(budget))
    brief = task_brief(episode) if arm.startswith("v0") else lab_brief(episode)
    if research_prompt.strip():
        brief = f"{research_prompt.strip()}\n\n{brief}"
    return agent_dir, brief


if __name__ == "__main__":
    arm, task_id, out = sys.argv[1:4]
    agent_dir, brief = materialize(arm, task_id, Path(out))
    (Path(out) / "brief.md").write_text(brief)
    print(agent_dir)
