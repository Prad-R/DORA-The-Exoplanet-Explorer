"""Run one v1 task with autonomous synthetic follow-up enabled.

Prerequisites: initialized Stargazer submodule, project virtualenv, and Omnigent.
"""
from pathlib import Path

from runner.batch import run_task


if __name__ == "__main__":
    result = run_task(
        "v1_lab",
        "seed96_diff3",
        Path("runs/observe-example").resolve(),
        max_observations=2,
        max_compute_rounds=3,
    )
    print(result)
