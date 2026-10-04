"""The runner must not record a usage-limit cut-off as a result, and must stop the batch."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import batch


class _FakeProc:
    returncode = 0

    def wait(self, timeout=None):
        return 0


@pytest.mark.parametrize("text,invalid", [
    ("You've hit your session limit · resets 7pm (America/New_York)", True),
    ("One planet found.", False),
])
def test_limit_cutoff_is_not_a_result(tmp_path, monkeypatch, text, invalid):
    out = tmp_path / "arm"
    out.mkdir()
    batch.stop.clear()

    def fake_popen(cmd, stdout, stderr, **kw):
        stdout.write(text)
        stderr.write("Omnigent session: http://127.0.0.1:6767/c/" + "a" * 32)
        return _FakeProc()

    def fake_run(cmd, **kw):
        if "export" in cmd:  # a session that reached the model
            Path(cmd[cmd.index("--output") + 1]).write_text(json.dumps(
                {"record_type": "session_meta", "llm_model": "m", "total_cost_usd": 0.1}) + "\n")
        return None

    monkeypatch.setattr(batch.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    monkeypatch.setattr(batch.shutil, "which", lambda name: name)
    r = batch.run_task("v0_plain", "seed44_diff2", out)
    assert bool(r.get("invalid")) is invalid
    assert (out / "seed44_diff2" / "result.json").exists() is not invalid
    assert batch.stop.is_set() is invalid
    if invalid:
        assert list((tmp_path / "arm_invalid").iterdir())
        assert batch.run_task("v0_plain", "seed96_diff3", out) is None  # nothing new starts
    batch.stop.clear()
