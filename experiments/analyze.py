"""Compare arms on the tasks both have finished.

    python experiments/analyze.py runs/v0 runs/v1

Prints per-tier pass rates, per-criterion rates, cost and the paired outcome table,
and writes experiments/results.md.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

TIERS = ["easy", "medium", "hard", "real", "all"]
CRITERIA = ["ok_delta_bic", "ok_rms", "ok_match", "ok_count"]


def load(run_dir: Path) -> dict:
    out = {}
    for path in sorted(run_dir.glob("*/result.json")):
        r = json.loads(path.read_text())
        r["group"] = "real" if r["task_id"].startswith("real_") else r["tier"]
        out[r["task_id"]] = r
    return out


def pct(xs: list) -> str:
    return f"{100 * sum(xs) / len(xs):.0f}% ({sum(xs)}/{len(xs)})" if xs else "-"


def mean(xs: list, fmt: str = "{:.2f}") -> str:
    xs = [x for x in xs if x is not None]
    return fmt.format(sum(xs) / len(xs)) if xs else "-"


def total_tokens(r: dict) -> int:
    return sum(r["tokens"].values())


def table(arms: dict, tasks: list) -> list:
    rows = ["| Tier | Arm | Solved | Submitted | Fit ok (BIC+RMS) | Count ok | Match ok | "
            "Subs | Repeat subs | Cost $ | Tokens k | Time s |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for tier in TIERS:
        for name, res in arms.items():
            rs = [res[t] for t in tasks if tier == "all" or res[t]["group"] == tier]
            if not rs:
                continue
            crit = lambda c: [bool(r["best_criteria"] and r["best_criteria"][c]) for r in rs]
            fit_ok = [a and b for a, b in zip(crit("ok_delta_bic"), crit("ok_rms"))]
            rows.append(
                f"| {tier} | {name} | {pct([r['solved'] for r in rs])} | {pct([r['submitted'] for r in rs])} | "
                f"{pct(fit_ok)} | {pct(crit('ok_count'))} | {pct(crit('ok_match'))} | "
                f"{mean([r['submissions'] for r in rs], '{:.1f}')} | "
                f"{sum(r['identical_resubmissions'] for r in rs)} | "
                f"{mean([r['cost_usd'] for r in rs])} | "
                f"{mean([total_tokens(r) / 1000 for r in rs], '{:.0f}')} | "
                f"{mean([r['duration_s'] for r in rs], '{:.0f}')} |"
            )
    return rows


def main() -> None:
    dirs = [Path(a) for a in sys.argv[1:]]
    arms = {d.name: load(d) for d in dirs}
    tasks = sorted(set.intersection(*(set(r) for r in arms.values())))
    lines = [f"# Results on {len(tasks)} tasks finished by every arm", ""]
    for name, res in arms.items():
        models = sorted({r["model"] or "?" for r in res.values()})
        lines.append(f"- `{name}`: {len(res)} tasks finished, model {', '.join(models)}")
    lines += [""] + table(arms, tasks)

    if len(arms) == 2:
        (a, ra), (b, rb) = arms.items()
        paired = defaultdict(list)
        for t in tasks:
            paired[(ra[t]["solved"], rb[t]["solved"])].append(t)
        lines += ["", f"## Paired outcomes ({a} vs {b})", "",
                  f"- both solved: {len(paired[(True, True)])}",
                  f"- only {a}: {len(paired[(True, False)])} {paired[(True, False)]}",
                  f"- only {b}: {len(paired[(False, True)])} {paired[(False, True)]}",
                  f"- neither: {len(paired[(False, False)])}"]
        ca = sum(ra[t]["cost_usd"] or 0 for t in tasks)
        cb = sum(rb[t]["cost_usd"] or 0 for t in tasks)
        sa, sb = sum(ra[t]["solved"] for t in tasks), sum(rb[t]["solved"] for t in tasks)
        lines += ["", "## Cost per solved task", "",
                  f"- {a}: ${ca:.2f} total, {sa} solved" + (f", ${ca / sa:.2f} each" if sa else ""),
                  f"- {b}: ${cb:.2f} total, {sb} solved" + (f", ${cb / sb:.2f} each" if sb else "")]
    leaks = [(n, t) for n, res in arms.items() for t, r in res.items() if r["leak_terms_in_tool_args"]]
    lines += ["", f"Tool calls that referenced benchmark internals: {leaks or 'none'}"]
    text = "\n".join(lines) + "\n"
    print(text)
    (Path(__file__).parent / "results.md").write_text(text)


if __name__ == "__main__":
    main()
