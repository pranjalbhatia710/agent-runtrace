from __future__ import annotations

import contextlib
import dataclasses
import json
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    keep = []
    for ch in text.lower().strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in {" ", "-", "_", "/"}:
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "run"


@dataclasses.dataclass
class TraceEvent:
    id: str
    type: str
    name: str
    started_at: str
    ended_at: Optional[str] = None
    parent_id: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    tags: Optional[List[str]] = None

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, sort_keys=True)


class Span:
    def __init__(self, recorder: "Recorder", event_type: str, name: str, input: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None):
        self.recorder = recorder
        self.event = TraceEvent(
            id=f"evt_{secrets.token_hex(6)}",
            type=event_type,
            name=name,
            started_at=_utc(),
            parent_id=recorder.current_event_id,
            input=input or {},
            tags=tags or [],
        )
        self._start = time.perf_counter()

    def __enter__(self) -> "Span":
        self.recorder._push(self.event.id)
        self.recorder._write_event(self.event)
        return self

    def set_output(self, output: Dict[str, Any]) -> None:
        self.event.output = output

    def set_error(self, error: BaseException | str) -> None:
        self.event.error = str(error)

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.event.ended_at = _utc()
        self.event.duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc is not None:
            self.event.error = str(exc)
        self.recorder._pop(self.event.id)
        self.recorder._write_event(self.event)
        return False


class Recorder:
    """Record agent runs as JSONL traces with optional command and git-diff capture."""

    def __init__(self, name: str = "agent-run", root: str | Path = ".agent-runs"):
        self.name = name
        self.root = Path(root)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = self.root / f"{timestamp}-{_slug(name)}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.run_dir / "trace.jsonl"
        self.metadata_path = self.run_dir / "metadata.json"
        self._stack: List[str] = []
        self._initial_git_diff = self._git_diff()
        self.metadata = {
            "name": name,
            "created_at": _utc(),
            "cwd": str(Path.cwd()),
            "version": "0.1.0",
            "trace_path": str(self.trace_path),
        }
        self._write_metadata()
        latest = self.root / "latest"
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(self.run_dir.resolve(), target_is_directory=True)
        except OSError:
            pass

    @property
    def current_event_id(self) -> Optional[str]:
        return self._stack[-1] if self._stack else None

    def _push(self, event_id: str) -> None:
        self._stack.append(event_id)

    def _pop(self, event_id: str) -> None:
        if self._stack and self._stack[-1] == event_id:
            self._stack.pop()
        elif event_id in self._stack:
            self._stack.remove(event_id)

    def _write_event(self, event: TraceEvent) -> None:
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    def _write_metadata(self) -> None:
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2, sort_keys=True), encoding="utf-8")

    @contextlib.contextmanager
    def span(self, event_type: str, name: str, input: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None) -> Iterator[Span]:
        with Span(self, event_type, name, input=input, tags=tags) as span:
            yield span

    def log(self, event_type: str, name: str, input: Optional[Dict[str, Any]] = None, output: Optional[Dict[str, Any]] = None, tags: Optional[List[str]] = None) -> TraceEvent:
        event = TraceEvent(
            id=f"evt_{secrets.token_hex(6)}",
            type=event_type,
            name=name,
            started_at=_utc(),
            ended_at=_utc(),
            parent_id=self.current_event_id,
            input=input or {},
            output=output or {},
            duration_ms=0,
            tags=tags or [],
        )
        self._write_event(event)
        return event

    def log_llm(self, name: str, prompt: str, response: str, model: Optional[str] = None, tokens: Optional[Dict[str, int]] = None) -> TraceEvent:
        return self.log(
            "llm",
            name,
            input={"model": model, "prompt": prompt},
            output={"response": response, "tokens": tokens or {}},
            tags=["llm"],
        )

    def run(self, cmd: Sequence[str] | str, cwd: str | Path | None = None, check: bool = False, timeout: Optional[int] = None, shell: bool = False) -> subprocess.CompletedProcess[str]:
        display = cmd if isinstance(cmd, str) else " ".join(cmd)
        with self.span("tool", "shell", input={"cmd": display, "cwd": str(cwd or Path.cwd()), "shell": shell}, tags=["shell"]) as span:
            try:
                result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, shell=shell, check=False)
                span.set_output({"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode})
                if check and result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                return result
            except Exception as exc:
                span.set_error(exc)
                raise

    def capture_file(self, path: str | Path, label: Optional[str] = None) -> Optional[Path]:
        source = Path(path)
        if not source.exists() or not source.is_file():
            self.log("file", label or str(source), input={"path": str(source)}, output={"captured": False, "reason": "missing"})
            return None
        files_dir = self.run_dir / "files"
        files_dir.mkdir(exist_ok=True)
        dest = files_dir / f"{secrets.token_hex(4)}-{source.name}"
        shutil.copy2(source, dest)
        self.log("file", label or source.name, input={"path": str(source)}, output={"captured": True, "artifact": str(dest)})
        return dest

    def _git_diff(self) -> str:
        try:
            result = subprocess.run(["git", "diff", "--"], text=True, capture_output=True, timeout=10)
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    def finish(self) -> Path:
        final_diff = self._git_diff()
        if final_diff and final_diff != self._initial_git_diff:
            diff_dir = self.run_dir / "diffs"
            diff_dir.mkdir(exist_ok=True)
            diff_path = diff_dir / "git.diff"
            diff_path.write_text(final_diff, encoding="utf-8")
            self.log("diff", "git diff", output={"artifact": str(diff_path), "bytes": len(final_diff.encode())}, tags=["git"])
        self.metadata["finished_at"] = _utc()
        self._write_metadata()
        return self.run_dir
