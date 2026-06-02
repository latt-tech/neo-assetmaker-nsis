"""Client helpers for the persistent material-core service process."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal


SERVICE_EXE_NAME = "material_core_service.exe"
SERVICE_SCRIPT_NAME = "material_service_main.py"


class MaterialServiceError(RuntimeError):
    """Raised when the persistent material service fails."""


def _creationflags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def resolve_service_command() -> list[str]:
    """Resolve the preferred command used to launch the material service."""

    current_executable = Path(sys.executable)
    candidate_paths = [
        current_executable.with_name(SERVICE_EXE_NAME),
        Path(__file__).resolve().parents[1] / SERVICE_EXE_NAME,
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return [str(candidate)]

    if getattr(sys, "frozen", False):
        raise MaterialServiceError(
            f"Required material service executable is missing: {SERVICE_EXE_NAME}"
        )

    script_path = Path(__file__).resolve().parents[1] / SERVICE_SCRIPT_NAME
    return [sys.executable, str(script_path)]


def spawn_material_service_process() -> subprocess.Popen[str]:
    """Start the persistent material service with text pipes."""

    try:
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
            "cwd": str(Path(__file__).resolve().parents[1]),
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = _creationflags()
        return subprocess.Popen(resolve_service_command(), **popen_kwargs)
    except OSError as exc:
        raise MaterialServiceError(
            f"Failed to launch material service: {exc}"
        ) from exc


@dataclass
class _PendingRequest:
    result_queue: "queue.Queue[dict[str, Any]]"
    progress_callback: Callable[[int, str], None] | None = None


def _clean_surrogate_chars(obj: Any) -> Any:
    """Remove invalid surrogate characters from strings."""
    if isinstance(obj, str):
        return "".join(c for c in obj if not (0xD800 <= ord(c) <= 0xDFFF))
    if isinstance(obj, dict):
        return {k: _clean_surrogate_chars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_surrogate_chars(item) for item in obj]
    return obj


class MaterialServiceClient:
    """Thread-safe client for the persistent material service process."""

    def __init__(self, *, default_timeout: float = 30.0):
        self._default_timeout = default_timeout
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._pending: dict[str, _PendingRequest] = {}
        self._pending_lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._request_counter = 0

    def request(
        self,
        command: str,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """Send a request to the service and wait for the final response."""

        process = self._ensure_process()
        return self._request_with_process(
            process,
            command,
            payload,
            timeout=timeout,
            progress_callback=progress_callback,
        )

    def _request_with_process(
        self,
        process: subprocess.Popen[str],
        command: str,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        request_id = self._next_request_id()
        pending = _PendingRequest(
            result_queue=queue.Queue(maxsize=1),
            progress_callback=progress_callback,
        )
        with self._pending_lock:
            self._pending[request_id] = pending

        cleaned_payload = _clean_surrogate_chars(payload)
        message = json.dumps(
            {
                "request_id": request_id,
                "command": command,
                "payload": cleaned_payload,
            },
            ensure_ascii=False,
        )

        try:
            with self._write_lock:
                assert process.stdin is not None
                process.stdin.write(f"{message}\n")
                process.stdin.flush()
        except Exception as exc:
            self._fail_pending_request(request_id)
            self._reset_process()
            raise MaterialServiceError(
                f"Failed to send request to material service: {exc}"
            ) from exc

        wait_timeout = self._default_timeout if timeout is None else timeout
        try:
            response = pending.result_queue.get(timeout=wait_timeout)
        except queue.Empty as exc:
            self._fail_pending_request(request_id)
            self._reset_process()
            raise MaterialServiceError(
                f"Material service timed out while handling '{command}'"
            ) from exc

        if response.get("type") == "failed":
            raise MaterialServiceError(str(response.get("message", "service failed")))

        return dict(response.get("payload", {}))

    def close(self) -> None:
        """Stop the service process and clear any pending requests."""

        with self._process_lock:
            process = self._process
        if process is None:
            return

        try:
            if process.poll() is None:
                self._request_with_process(process, "shutdown", {}, timeout=2.0)
        except MaterialServiceError:
            pass
        finally:
            self._reset_process()

    def _ensure_process(self) -> subprocess.Popen[str]:
        with self._process_lock:
            process = self._process
            if process is not None and process.poll() is None:
                return process

            process = spawn_material_service_process()
            self._process = process
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                args=(process,),
                name="MaterialServiceReader",
                daemon=True,
            )
            self._reader_thread.start()
            return process

    def _next_request_id(self) -> str:
        with self._process_lock:
            self._request_counter += 1
            return str(self._request_counter)

    def _reader_loop(self, process: subprocess.Popen[str]) -> None:
        disconnect_message = "Material service disconnected"
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                message = json.loads(line)
                message_type = str(message.get("type", ""))
                request_id = str(message.get("request_id", ""))

                if not request_id:
                    continue

                with self._pending_lock:
                    pending = self._pending.get(request_id)

                if pending is None:
                    if message_type == "failed" and request_id == "unknown":
                        disconnect_message = str(
                            message.get("message", "Material service failed")
                        )
                        break
                    continue

                if message_type == "progress":
                    if pending.progress_callback is not None:
                        pending.progress_callback(
                            int(message.get("percent", 0)),
                            str(message.get("message", "")),
                        )
                    continue

                if message_type in {"result", "failed"}:
                    with self._pending_lock:
                        self._pending.pop(request_id, None)
                    pending.result_queue.put(message)
        except Exception as exc:
            disconnect_message = str(exc)
        finally:
            try:
                if process.stderr is not None and process.poll() is not None:
                    stderr_output = process.stderr.read().strip()
                    if stderr_output:
                        disconnect_message = stderr_output
            except Exception:
                pass
            self._handle_disconnect(process, disconnect_message)

    def _handle_disconnect(
        self,
        process: subprocess.Popen[str],
        message: str,
    ) -> None:
        with self._process_lock:
            if self._process is process:
                self._process = None
                self._reader_thread = None

        with self._pending_lock:
            pending_items = list(self._pending.items())
            self._pending.clear()

        for _request_id, pending in pending_items:
            pending.result_queue.put(
                {
                    "type": "failed",
                    "message": message or "Material service disconnected",
                }
            )

    def _fail_pending_request(self, request_id: str) -> None:
        with self._pending_lock:
            self._pending.pop(request_id, None)

    def _reset_process(self) -> None:
        with self._process_lock:
            process = self._process
            self._process = None
            self._reader_thread = None

        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

        with self._pending_lock:
            pending_items = list(self._pending.items())
            self._pending.clear()

        for _request_id, pending in pending_items:
            pending.result_queue.put(
                {
                    "type": "failed",
                    "message": "Material service stopped",
                }
            )


class MaterialServiceCommandThread(QThread):
    """Qt wrapper for running a material-service request off the UI thread."""

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(
        self,
        service_client: MaterialServiceClient,
        command: str,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service_client = service_client
        self._command = command
        self._payload = payload
        self._timeout = timeout

    def run(self) -> None:
        try:
            result = self._service_client.request(
                self._command,
                self._payload,
                timeout=self._timeout,
                progress_callback=self.progress.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


__all__ = [
    "MaterialServiceClient",
    "MaterialServiceCommandThread",
    "MaterialServiceError",
    "SERVICE_EXE_NAME",
    "resolve_service_command",
    "spawn_material_service_process",
]
