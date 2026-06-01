import subprocess
import sys

from agent_runtrace import Recorder
from agent_runtrace.viewer import load_events, write_viewer


def test_recorder_logs_llm_and_shell(tmp_path):
    rec = Recorder("unit test", root=tmp_path / ".agent-runs")
    rec.log_llm("plan", "prompt", "response", model="demo")
    result = rec.run([sys.executable, "-c", "print('ok')"])
    run_dir = rec.finish()
    assert result.returncode == 0
    events = load_events(run_dir)
    assert [event["type"] for event in events] == ["llm", "tool"]
    assert events[1]["output"]["stdout"].strip() == "ok"


def test_viewer_writes_standalone_html(tmp_path):
    rec = Recorder("viewer test", root=tmp_path / ".agent-runs")
    rec.log("note", "hello", output={"ok": True})
    run_dir = rec.finish()
    html_path = write_viewer(run_dir)
    html = html_path.read_text(encoding="utf-8")
    assert "agent-runtrace" in html
    assert "hello" in html


def test_shell_failure_is_recorded_without_raising_by_default(tmp_path):
    rec = Recorder("failure test", root=tmp_path / ".agent-runs")
    result = rec.run([sys.executable, "-c", "raise SystemExit(7)"])
    run_dir = rec.finish()
    events = load_events(run_dir)
    assert result.returncode == 7
    assert events[0]["output"]["exit_code"] == 7


def test_shell_check_raises_and_records_error(tmp_path):
    rec = Recorder("check failure", root=tmp_path / ".agent-runs")
    try:
        rec.run([sys.executable, "-c", "raise SystemExit(3)"], check=True)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("expected CalledProcessError")
    run_dir = rec.finish()
    events = load_events(run_dir)
    assert events[0]["error"]
