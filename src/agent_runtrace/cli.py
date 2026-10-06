from __future__ import annotations

import argparse
import json
import sys
import webbrowser
import zipfile
from pathlib import Path

from .recorder import Recorder
from .viewer import load_events, write_viewer


def _resolve_run(path: str) -> Path:
    p = Path(".agent-runs/latest") if path == "latest" else Path(path)
    if not p.exists():
        raise SystemExit(f"run not found: {p}")
    return p.resolve()


def cmd_run(args: argparse.Namespace) -> int:
    if not args.cmd:
        raise SystemExit("usage: agent-runtrace run -- <command>")
    rec = Recorder(args.name, redact_patterns=args.redact)
    result = rec.run(args.cmd, shell=False)
    run_dir = rec.finish()
    print(f"trace: {run_dir}")
    print(f"exit_code: {result.returncode}")
    return result.returncode if args.preserve_exit_code else 0


def cmd_demo(args: argparse.Namespace) -> int:
    rec = Recorder("demo failing test agent")
    rec.log_llm("plan", "Fix the failing unit test.", "I will inspect the failure, patch the code, and rerun tests.", model="demo-model")
    rec.run([sys.executable, "-c", "print('tests::test_addition FAILED'); raise SystemExit(1)"])
    rec.log_llm("repair", "The test failed. What next?", "The assertion expects 4, so I will change the sample function output.", model="demo-model")
    rec.run([sys.executable, "-c", "print('tests::test_addition PASSED')"])
    run_dir = rec.finish()
    html = write_viewer(run_dir)
    print(f"demo trace: {run_dir}")
    print(f"viewer: {html}")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    html_path = write_viewer(run_dir)
    print(str(html_path))
    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    events = load_events(run_dir)
    failures = [e for e in events if e.get("error") or (isinstance(e.get("output"), dict) and e["output"].get("exit_code") not in (None, 0))]
    total_duration_ms = sum(e.get("duration_ms") or 0 for e in events)
    slowest = max(events, key=lambda e: e.get("duration_ms") or 0, default=None)
    over_budget = args.max_total_duration_ms is not None and total_duration_ms > args.max_total_duration_ms
    event_types = sorted({e["type"] for e in events})
    missing_types = sorted(set(args.require_event_type or []) - set(event_types))
    print(
        json.dumps(
            {
                "run": str(run_dir),
                "events": len(events),
                "failures": len(failures),
                "failed_events": [e.get("name") for e in failures],
                "total_duration_ms": total_duration_ms,
                "max_total_duration_ms": args.max_total_duration_ms,
                "over_duration_budget": over_budget,
                "required_event_types": args.require_event_type or [],
                "missing_event_types": missing_types,
                "slowest_event": None
                if slowest is None
                else {
                    "name": slowest.get("name"),
                    "type": slowest.get("type"),
                    "duration_ms": slowest.get("duration_ms") or 0,
                },
                "types": event_types,
            },
            indent=2,
        )
    )
    if args.fail_on_failure and failures:
        return 1
    if over_budget:
        return 1
    if missing_types:
        return 1
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    if args.with_viewer:
        write_viewer(run_dir)
    out = Path(args.out or f"{run_dir.name}.agenttrace.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in run_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(run_dir.parent))
    print(str(out))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-runtrace", description="Record and inspect local AI-agent run traces.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="record a shell command as a trace")
    run.add_argument("--name", default="shell-command")
    run.add_argument("--preserve-exit-code", action="store_true", help="return the wrapped command exit code")
    run.add_argument("--redact", action="append", default=[], help="regex pattern to replace with [REDACTED] in recorded event payloads; repeat for multiple patterns")
    run.add_argument("cmd", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)
    demo = sub.add_parser("demo", help="create a no-API-key demo trace")
    demo.set_defaults(func=cmd_demo)
    view = sub.add_parser("view", help="write a standalone HTML viewer for a run")
    view.add_argument("run", nargs="?", default="latest")
    view.add_argument("--open", action="store_true")
    view.set_defaults(func=cmd_view)
    inspect = sub.add_parser("inspect", help="print a JSON summary of a run")
    inspect.add_argument("run", nargs="?", default="latest")
    inspect.add_argument("--fail-on-failure", action="store_true", help="exit 1 when the inspected trace contains failed events")
    inspect.add_argument(
        "--max-total-duration-ms",
        type=int,
        default=None,
        help="exit 1 when summed event duration exceeds this millisecond budget",
    )
    inspect.add_argument(
        "--require-event-type",
        action="append",
        default=[],
        help="exit 1 unless the trace includes this event type; repeat for multiple required types",
    )
    inspect.set_defaults(func=cmd_inspect)
    export = sub.add_parser("export", help="export a run as a .agenttrace.zip bundle")
    export.add_argument("run", nargs="?", default="latest")
    export.add_argument("--out")
    export.add_argument("--with-viewer", action="store_true", help="generate and include the standalone HTML viewer before zipping")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "cmd", None) and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    if getattr(args, "max_total_duration_ms", None) is not None and args.max_total_duration_ms < 0:
        raise SystemExit("--max-total-duration-ms must be zero or greater")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
