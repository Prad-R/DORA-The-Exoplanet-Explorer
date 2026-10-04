# Exoplanet lab

An agent lab that finds planets in radial-velocity data, and asks for more telescope time when the data cannot settle the answer.

Built for the Hack-Nation × Databricks "Agentic Scientific Discovery" challenge ([docs/PS.pdf](docs/PS.pdf)) on the [Stargazer](https://github.com/AIPS-UofT/Stargazer) benchmark ([docs/Stargazer.pdf](docs/Stargazer.pdf)). Agents run on Omnigent.

## What it does

Each task is a star with a set of velocity measurements. The lab must report how many planets orbit it and their orbits.

Two arms run on the same tasks:

| Arm | What it is |
|---|---|
| `v0_plain` | One agent with a Python REPL and a submit tool. The baseline. |
| `v1_lab` | A lead agent with an analyst, an investigator and a critic, sharing a research record. |

The lab arm works in a loop:

1. Propose candidate planetary systems and fit each one.
2. Have the critic review the leading fit.
3. Apply a numerical decision rule ([lab/decide.py](lab/decide.py)): conclude, review, refine, or observe.
4. If the data cannot separate the competing models, schedule follow-up observations, refit, and decide again.

Follow-up observations are simulated from the task's true planets, with white noise and jitter.

## Layout

| Path | Contents |
|---|---|
| [agents/](agents/) | Omnigent agent definitions for both arms |
| [lab/](lab/) | Tool servers, fitting ([lab/rv.py](lab/rv.py)), decision rule, episode state, report rendering |
| [runner/](runner/) | Batch runner: one headless Omnigent session per task |
| [ui/](ui/) | Local web interface for starting and watching runs |
| [experiments/](experiments/) | Task lists, analysis scripts, no-model baselines |
| [runs/](runs/) | Recorded runs |
| [tests/](tests/) | Unit tests |
| [third_party/Stargazer](third_party/Stargazer) | The benchmark, as a git submodule |

## Setup

```bash
git clone --recurse-submodules git@github.com:Prad-R/exoplanets.git
cd exoplanets
```

You need a Python environment at `.venv` with Omnigent, the Stargazer package from the submodule, `numpy`, `scipy` and `pytest`. Omnigent must be signed in to a model provider.

## Run

Agent runs call a paid model. Start with one task.

```bash
# Baseline arm on one task
.venv/bin/python runner/batch.py --arm v0_plain --tasks seed96_diff3 --out runs/v0

# Lab arm on a task list, capped at $20
.venv/bin/python runner/batch.py --arm v1_lab --tasks experiments/demo_tasks.txt \
    --out runs/v1_obs --workers 1 --max-cost 20
```

`--tasks` takes a file with one task id per line, or comma-separated ids. Finished tasks are skipped on rerun.

| Option | Default | Meaning |
|---|---|---|
| `--workers` | 2 | Tasks run in parallel |
| `--max-cost` | none | Stop starting tasks once this many dollars are spent |
| `--max-observations` | 30 | Total follow-up points per task |
| `--obs-per-campaign` | 10 | Follow-up points per observing campaign |
| `--max-compute-rounds` | 4 | Refit rounds per task |
| `--prompt` | empty | Research prompt added before the task brief |
| `--live-logs` | off | Show Omnigent output in the terminal |

Each task writes `runs/<out>/<task>/` with the transcript, tool-server state and `result.json`.

### Web interface

```bash
.venv/bin/python ui/server.py        # opens http://127.0.0.1:8765
```

### Tests and analysis

```bash
.venv/bin/python -m pytest -q tests          # no model calls
.venv/bin/python experiments/analyze.py      # summarise recorded runs
.venv/bin/python experiments/paper_table.py  # compare with the Stargazer paper
```

## Results

Baseline arm on all 120 tasks, from [experiments/paper_table.md](experiments/paper_table.md):

| | Easy | Medium | Hard | Real |
|---|---|---|---|---|
| `v0_plain`, claude-opus-5-5 | 7/20 | 5/40 | 0/40 | 0/20 |
| Classical pipeline (paper) | 95% | 35% | 5% | n/a |

The lab arm has recorded runs in [runs/v1_obs](runs/v1_obs) and [runs/v1_representative](runs/v1_representative). It has not been run on the full benchmark.

## Limits

- Follow-up observations come from the task's true planets. This is a simulated telescope, not new data.
- The lab arm gets more tool calls and more data than the baseline, so the two arms are not a matched comparison.
- Simulated follow-ups leave out the correlated stellar noise that 40% of synthetic tasks contain.
