import json
import os
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

from agent_runtrace import Recorder
from agent_runtrace.cli import main
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


def test_shell_command_input_keeps_argv_and_quoted_display(tmp_path):
    rec = Recorder("argv trace", root=tmp_path / ".agent-runs")
    rec.run([sys.executable, "-c", "print('two words')"])
    run_dir = rec.finish()

    event = load_events(run_dir)[0]

    assert event["input"]["argv"] == [sys.executable, "-c", "print('two words')"]
    assert event["input"]["cmd"] == shlex.join([sys.executable, "-c", "print('two words')"])


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


def test_shell_timeout_records_structured_timeout_output(tmp_path):
    rec = Recorder("timeout failure", root=tmp_path / ".agent-runs")
    try:
        rec.run([sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.01)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("expected TimeoutExpired")

    run_dir = rec.finish()
    events = load_events(run_dir)

    assert events[0]["error"]
    assert events[0]["output"]["timed_out"] is True
    assert events[0]["output"]["timeout"] == 0.01


def test_redact_patterns_apply_to_nested_event_payloads(tmp_path):
    rec = Recorder("redaction", root=tmp_path / ".agent-runs", redact_patterns=[r"sk-[A-Za-z0-9]+"])
    rec.log_llm("call", "token sk-secret123", "response sk-secret456", model="demo")
    run_dir = rec.finish()

    events = load_events(run_dir)
    raw_trace = (run_dir / "trace.jsonl").read_text(encoding="utf-8")
    assert events[0]["input"]["prompt"] == "token [REDACTED]"
    assert events[0]["output"]["response"] == "response [REDACTED]"
    assert "sk-secret" not in raw_trace


def test_run_cli_redact_flag_scrubs_shell_output(tmp_path):
    old_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        exit_code = main([
            "run",
            "--redact",
            r"sk-[A-Za-z0-9]+",
            "--",
            sys.executable,
            "-c",
            "print('token sk-cli123')",
        ])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    trace = next((tmp_path / ".agent-runs" / "latest").resolve().glob("trace.jsonl"))
    raw_trace = trace.read_text(encoding="utf-8")
    event = json.loads(raw_trace.splitlines()[-1])
    assert event["output"]["stdout"].strip() == "token [REDACTED]"
    assert "sk-cli123" not in raw_trace


def test_inspect_cli_reports_failure_names_and_duration(tmp_path):
    rec = Recorder("inspect summary", root=tmp_path / ".agent-runs")
    rec.log("note", "planned", output={"ok": True})
    rec.run([sys.executable, "-c", "raise SystemExit(4)"])
    run_dir = rec.finish()

    with patch("sys.argv", ["agent-runtrace"]), patch("builtins.print") as printed:
        exit_code = main(["inspect", str(run_dir)])

    assert exit_code == 0
    payload = json.loads(printed.call_args.args[0])
    assert payload["events"] == 2
    assert payload["failures"] == 1
    assert payload["failed_events"] == ["shell"]
    assert payload["total_duration_ms"] >= 0
    assert payload["slowest_event"]["duration_ms"] >= 0
    assert payload["over_duration_budget"] is False


def test_inspect_cli_can_fail_when_trace_exceeds_duration_budget(tmp_path):
    run_dir = tmp_path / "slow-run"
    run_dir.mkdir()
    (run_dir / "trace.jsonl").write_text(
        json.dumps({"id": "evt_fast", "type": "llm", "name": "plan", "duration_ms": 15})
        + "\n"
        + json.dumps({"id": "evt_slow", "type": "tool", "name": "pytest", "duration_ms": 90})
        + "\n",
        encoding="utf-8",
    )

    with patch("builtins.print") as printed:
        exit_code = main(["inspect", str(run_dir), "--max-total-duration-ms", "100"])

    assert exit_code == 1
    payload = json.loads(printed.call_args.args[0])
    assert payload["total_duration_ms"] == 105
    assert payload["max_total_duration_ms"] == 100
    assert payload["over_duration_budget"] is True
    assert payload["slowest_event"] == {"name": "pytest", "type": "tool", "duration_ms": 90}


def test_inspect_cli_rejects_negative_duration_budget():
    try:
        main(["inspect", "latest", "--max-total-duration-ms", "-1"])
    except SystemExit as exc:
        assert str(exc) == "--max-total-duration-ms must be zero or greater"
    else:
        raise AssertionError("expected SystemExit")


def test_inspect_cli_can_fail_when_trace_contains_failures(tmp_path):
    rec = Recorder("inspect failure gate", root=tmp_path / ".agent-runs")
    rec.run([sys.executable, "-c", "raise SystemExit(9)"])
    run_dir = rec.finish()

    with patch("builtins.print"):
        exit_code = main(["inspect", str(run_dir), "--fail-on-failure"])

    assert exit_code == 1


def test_export_cli_can_include_standalone_viewer(tmp_path):
    rec = Recorder("export viewer", root=tmp_path / ".agent-runs")
    rec.log("note", "ship trace", output={"ok": True})
    run_dir = rec.finish()
    out = tmp_path / "trace.agenttrace.zip"

    exit_code = main(["export", str(run_dir), "--with-viewer", "--out", str(out)])

    assert exit_code == 0
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert f"{run_dir.name}/index.html" in names
    assert f"{run_dir.name}/trace.jsonl" in names
