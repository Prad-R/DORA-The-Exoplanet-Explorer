"""The local UI exposes datasets without leaking synthetic truth."""
import json
import io
from unittest.mock import Mock, patch

from ui import server


def test_task_preview_contains_observations_not_truth():
    preview = server.task_preview("seed96_diff3")
    assert preview["observations"]["times_days"]
    serialized = json.dumps(preview)
    assert '"planets"' not in serialized
    assert '"config"' not in serialized


def test_catalog_lists_synthetic_and_real_tasks():
    tasks = server.task_catalog()
    assert any(t["id"] == "seed96_diff3" and t["bank"] == "synthetic" for t in tasks)
    assert any(t["id"].startswith("real_") and t["bank"] == "real" for t in tasks)


def test_start_run_uses_existing_v1_runner(tmp_path):
    fake = Mock()
    fake.stdout = io.StringIO("")
    fake.wait.return_value = 0
    with patch.object(server, "RUNS", tmp_path), patch.object(server.subprocess, "Popen", return_value=fake) as popen:
        meta = server.start_run({"task_id": "seed96_diff3", "prompt": "Test aliases",
                                 "max_observations": 2, "max_compute_rounds": 3})
    command = popen.call_args.args[0]
    assert command[command.index("--arm") + 1] == "v1_lab"
    assert command[command.index("--prompt") + 1] == "Test aliases"
    assert command[command.index("--max-observations") + 1] == "2"
    assert (tmp_path / meta["run_id"] / "ui.json").exists()


def test_run_snapshot_reads_existing_formats(tmp_path):
    run_id, task = "run-1", "seed96_diff3"
    root = tmp_path / run_id
    state = root / task / "state"
    state.mkdir(parents=True)
    (root / "ui.json").write_text(json.dumps({"run_id": run_id, "task_id": task}))
    (state / "ledger.jsonl").write_text(json.dumps({"kind": "decision", "status": "unresolved"}) + "\n")
    with patch.object(server, "RUNS", tmp_path):
        result = server.run_snapshot(run_id)
    assert result["ledger"][0]["status"] == "unresolved"
    assert result["running"] is False
