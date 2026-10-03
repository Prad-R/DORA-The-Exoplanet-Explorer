"""Stargazer Table 1 layout for one or more arms.

    python experiments/paper_table.py runs/v0 [runs/v1 ...]

Pass Rate: all four criteria met. Env Done: the episode ended on its own rather
than being cut off by the time limit or the tool-call cap. Columns show percent
and (passed/finished tasks). One run per task, so there is no Pass@3 column.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOTAL = {"easy": 20, "medium": 40, "hard": 40, "real": 20}
# Table 1 of the paper (mean of three runs), for reference.
PAPER = [
    ("Classical Pipeline (paper)", "95.0", "35.0", "5.0", "100", "100", "100", "-"),
    ("GPT-5.3-codex (paper, best LLM)", "80.0", "30.8", "4.2", "88.3", "48.3", "7.5", "0.0"),
    ("Claude-Sonnet-4.6 (paper)", "68.3", "22.5", "0.8", "68.3", "28.3", "0.8", "0.0"),
]


def load(run_dir: Path) -> dict:
    groups = {k: [] for k in TOTAL}
    for path in sorted(run_dir.glob("*/result.json")):
        r = json.loads(path.read_text())
        budget = json.loads((path.parent / "budget.json").read_text())
        calls = sum(n for name, n in r["tool_calls"].items() if name != "ToolSearch")
        r["env_done"] = not r["timed_out"] and r["exit_code"] == 0 and calls < budget["max_tool_calls"]
        groups["real" if r["task_id"].startswith("real_") else r["tier"]].append(r)
    return groups


def cell(rs: list, key: str) -> str:
    if not rs:
        return "-"
    n = sum(bool(r[key]) for r in rs)
    return f"{100 * n / len(rs):.1f} ({n}/{len(rs)})"


def main() -> None:
    lines = ["| Model | Pass Easy | Pass Med | Pass Hard | Done Easy | Done Med | Done Hard | Real |",
             "|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(row) + " |" for row in PAPER]
    notes = []
    for arg in sys.argv[1:]:
        g = load(Path(arg))
        model = next((r["model"] for rs in g.values() for r in rs if r["model"]), "?")
        lines.append(
            f"| **{Path(arg).name}, {model} (ours, Omnigent)** | "
            + " | ".join(cell(g[t], "solved") for t in ("easy", "medium", "hard"))
            + " | " + " | ".join(cell(g[t], "env_done") for t in ("easy", "medium", "hard"))
            + f" | {cell(g['real'], 'solved')} |"
        )
        notes.append(f"{Path(arg).name}: " + ", ".join(f"{t} {len(g[t])}/{TOTAL[t]} tasks run" for t in TOTAL))
    text = "\n".join(lines + [""] + notes) + "\n"
    print(text)
    (Path(__file__).parent / "paper_table.md").write_text(text)


if __name__ == "__main__":
    main()
