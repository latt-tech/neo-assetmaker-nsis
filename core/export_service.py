"""
Export service facade for material package generation.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from config.epconfig import EPConfig
from core.export_models import MaterialExportRequest, VideoExportParams
from core.material_worker_client import spawn_worker_process
from core.video_processor import find_ffmpeg

logger = logging.getLogger(__name__)


class ExportWorker(QThread):
    """Worker thread that streams progress from the isolated export process."""

    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._request: Optional[MaterialExportRequest] = None
        self._ffmpeg_path: str = ""
        self._cancelled: bool = False
        self._process: Optional[subprocess.Popen[str]] = None

    def setup(
        self,
        request: MaterialExportRequest,
        ffmpeg_path: str = "",
    ) -> None:
        self._request = request
        self._ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def run(self) -> None:
        try:
            if self._request is None:
                self.export_failed.emit("Export request is not initialized")
                return

            os.makedirs(self._request.output_dir, exist_ok=True)
            self._process = spawn_worker_process()
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            assert self._process.stderr is not None

            request_payload = json.dumps(
                {
                    "command": "export",
                    "payload": self._request.to_dict(ffmpeg_path=self._ffmpeg_path),
                },
                ensure_ascii=False,
            )
            self._process.stdin.write(f"{request_payload}\n")
            self._process.stdin.close()

            completed_message = ""
            for raw_line in self._process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                message = json.loads(line)
                message_type = message.get("type")
                if message_type == "progress":
                    self.progress_updated.emit(
                        int(message.get("percent", 0)),
                        str(message.get("message", "")),
                    )
                elif message_type == "completed":
                    completed_message = str(
                        message.get("message", "Export completed")
                    )
                elif message_type == "failed":
                    self._process.wait()
                    self.export_failed.emit(
                        str(message.get("message", "Export failed"))
                    )
                    return

            stderr_output = self._process.stderr.read().strip()
            return_code = self._process.wait()

            if self._cancelled:
                self.export_failed.emit("Export cancelled")
                return
            if return_code != 0:
                self.export_failed.emit(stderr_output or "Material worker failed")
                return

            self.progress_updated.emit(100, "Export completed")
            self.export_completed.emit(completed_message or "Export completed")
        except Exception as exc:
            logger.exception("Export failed")
            self.export_failed.emit(f"Export failed: {exc}")
        finally:
            self._process = None


class ExportService(QObject):
    """Thin export facade that delegates heavy work to the material worker."""

    progress_updated = pyqtSignal(int, str)
    export_completed = pyqtSignal(str)
    export_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[ExportWorker] = None
        self._ffmpeg_path: str = ""

    @property
    def is_exporting(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def ffmpeg_available(self) -> bool:
        if not self._ffmpeg_path:
            self._ffmpeg_path = find_ffmpeg()
        return bool(self._ffmpeg_path)

    def export_all(
        self,
        output_dir: str,
        base_dir: str,
        epconfig: EPConfig,
        icon_path: str = "",
        loop_video_params: Optional[VideoExportParams] = None,
        intro_video_params: Optional[VideoExportParams] = None,
        loop_image_path: Optional[str] = None,
    ) -> None:
        if self.is_exporting:
            self.export_failed.emit("An export job is already running")
            return

        if isinstance(loop_video_params, dict):
            loop_video_params = VideoExportParams.from_dict(loop_video_params)
        if isinstance(intro_video_params, dict):
            intro_video_params = VideoExportParams.from_dict(intro_video_params)

        request = MaterialExportRequest(
            base_dir=base_dir,
            output_dir=output_dir,
            config=epconfig.to_dict(),
            icon_path=icon_path,
            loop_image_path=loop_image_path or "",
            loop_video_params=loop_video_params,
            intro_video_params=intro_video_params,
        )
        if request.requires_ffmpeg() and not self.ffmpeg_available:
            self.export_failed.emit("FFmpeg is required for video export")
            return

        self._worker = ExportWorker(self)
        self._worker.setup(request=request, ffmpeg_path=self._ffmpeg_path)
        self._worker.progress_updated.connect(self.progress_updated.emit)
        self._worker.export_completed.connect(self._on_completed)
        self._worker.export_failed.connect(self._on_failed)
        self._worker.start()

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _on_completed(self, message: str) -> None:
        self.export_completed.emit(message)
        self._cleanup()

    def _on_failed(self, message: str) -> None:
        self.export_failed.emit(message)
        self._cleanup()

    def _cleanup(self) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None


__all__ = ["ExportService", "VideoExportParams"]
