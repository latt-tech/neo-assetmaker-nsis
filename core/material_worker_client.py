"""Helpers for launching the isolated material-core worker."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


WORKER_EXE_NAME = "material_core_worker.exe"


class MaterialWorkerError(RuntimeError):
    """Raised when the isolated worker cannot be launched or fails."""


def _creationflags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def resolve_worker_command() -> list[str]:
    """Resolve the preferred command used to launch the worker."""

    current_executable = Path(sys.executable)
    candidate_paths = [
        current_executable.with_name(WORKER_EXE_NAME),
        Path(__file__).resolve().parents[1] / WORKER_EXE_NAME,
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return [str(candidate)]

    return [sys.executable, "-m", "protected_worker.worker_main"]


def spawn_worker_process() -> subprocess.Popen[str]:
    """Start the worker subprocess with text pipes."""

    try:
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": str(Path(__file__).resolve().parents[1]),
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = _creationflags()
        return subprocess.Popen(
            resolve_worker_command(),
            **popen_kwargs,
        )
    except OSError as exc:
        raise MaterialWorkerError(f"Failed to launch material worker: {exc}") from exc


def run_worker_validation(
    config: dict[str, Any],
    *,
    base_dir: str = "",
) -> list[dict[str, str]]:
    """Validate EPConfig data in the isolated worker."""

    process = spawn_worker_process()
    request = json.dumps(
        {
            "command": "validate",
            "payload": {
                "config": config,
                "base_dir": base_dir,
            },
        },
        ensure_ascii=False,
    )

    stdout, stderr = process.communicate(f"{request}\n")
    if process.returncode != 0:
        detail = stderr.strip() or stdout.strip() or "worker failed"
        raise MaterialWorkerError(detail)

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        if message.get("type") == "result":
            return list(message.get("results", []))
        if message.get("type") == "failed":
            raise MaterialWorkerError(str(message.get("message", "worker failed")))

    raise MaterialWorkerError("Material worker did not return validation results")
