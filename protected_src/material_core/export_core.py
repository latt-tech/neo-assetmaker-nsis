"""Protected export implementation compiled into a native extension."""

from __future__ import annotations

import json
import logging
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

try:
    import av

    HAS_AV = True
except ImportError:  # pragma: no cover - dependency probe
    HAS_AV = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:  # pragma: no cover - dependency probe
    HAS_CV2 = False

from config.constants import get_resolution_spec
from core.video_processor import X264_PARAMS

logger = logging.getLogger(__name__)

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[int, str], None]


class ProtectedExportRuntime:
    """Runtime services shared by protected export operations."""

    def __init__(
        self,
        *,
        ffmpeg_path: str,
        output_dir: str,
        progress_callback: ProgressCallback,
        cancel_check: CancelCheck,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.output_dir = output_dir
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check
        self._ffmpeg_process: subprocess.Popen | None = None

    def emit_progress(self, percent: int, message: str) -> None:
        self._progress_callback(percent, message)

    def is_cancelled(self) -> bool:
        return self._cancel_check()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise InterruptedError("导出已取消")

    def cancel(self) -> None:
        process = self._ffmpeg_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Failed to terminate ffmpeg process: %s", exc)

    def set_ffmpeg_process(self, process: subprocess.Popen | None) -> None:
        self._ffmpeg_process = process


def execute_task(
    *,
    export_type: str,
    output_path: str,
    data: Any,
    runtime: ProtectedExportRuntime,
    base_progress: int,
    total_tasks: int,
    task_label: str,
) -> None:
    """Execute one export task inside the protected core."""
    runtime.raise_if_cancelled()
    runtime.emit_progress(base_progress, f"正在导出 {task_label}...")

    if export_type in {"logo", "overlay"}:
        write_argb(output_path, data, runtime.is_cancelled)
        return

    if export_type == "icon":
        write_icon_png(output_path, data)
        return

    if export_type in {"loop", "intro"}:
        export_video(
            output_path=output_path,
            params=data,
            runtime=runtime,
            base_progress=base_progress,
            total_tasks=total_tasks,
        )
        return

    raise ValueError(f"Unsupported export task type: {export_type}")


def write_argb(output_path: str, mat: np.ndarray, is_cancelled: CancelCheck) -> None:
    """Write a rotated image buffer as raw BGRA bytes."""
    rotated = cv2.rotate(mat, cv2.ROTATE_180) if HAS_CV2 else np.rot90(mat, 2)
    rotated = rotated.astype(np.uint8)
    height, width = rotated.shape[:2]
    channels = rotated.shape[-1] if len(rotated.shape) == 3 else 1

    with open(output_path, "wb") as file_obj:
        for y in range(height):
            if is_cancelled():
                raise InterruptedError("导出已取消")
            for x in range(width):
                if channels == 4:
                    b, g, r, a = rotated[y, x]
                elif channels == 3:
                    b, g, r = rotated[y, x]
                    a = 255
                else:
                    b = g = r = rotated[y, x]
                    a = 255
                file_obj.write(struct.pack("BBBB", b, g, r, a))


def write_icon_png(output_path: str, mat: np.ndarray) -> bool:
    """Encode an icon as PNG without exposing the encoding logic in the facade."""
    if not HAS_CV2:
        return False
    success, encoded = cv2.imencode(".png", mat)
    if not success:
        return False
    with open(output_path, "wb") as file_obj:
        file_obj.write(encoded.tobytes())
    return True


def save_epconfig(output_path: str, config_dict: dict[str, Any]) -> None:
    """Persist normalized EPConfig content."""
    with open(output_path, "w", encoding="utf-8") as file_obj:
        json.dump(config_dict, file_obj, ensure_ascii=False, indent=4)


def build_frame_pattern(temp_dir: str) -> str:
    """Return the normalized ffmpeg frame input pattern."""
    return f"{Path(temp_dir).as_posix()}/frame_%06d.png"


def export_video(
    *,
    output_path: str,
    params: Any,
    runtime: ProtectedExportRuntime,
    base_progress: int,
    total_tasks: int,
) -> None:
    """Export video content from either a source video or a source image."""
    if not runtime.ffmpeg_path:
        raise RuntimeError("未找到ffmpeg，无法导出视频")
    if not HAS_CV2:
        raise RuntimeError("未安装opencv-python，无法处理视频")
    if not HAS_AV:
        raise RuntimeError("未安装PyAV，无法解码视频")

    if params.is_image:
        export_video_from_image(
            output_path=output_path,
            params=params,
            runtime=runtime,
            base_progress=base_progress,
            total_tasks=total_tasks,
        )
        return

    spec = get_resolution_spec(params.resolution)
    target_w = spec["width"]
    target_h = spec["height"]
    padded_w = spec["padded_width"]
    padded_h = spec["padded_height"]
    rotate_180 = spec["rotate_180"]

    temp_dir = os.path.join(runtime.output_dir, "_temp_frames").replace("\\", "/")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        container = av.open(params.video_path)
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"

        total_frames = params.end_frame - params.start_frame
        rotation = params.rotation
        orig_w = stream.width
        orig_h = stream.height
        rot_matrix = None
        rotated_size = None

        if rotation not in (0, 90, 180, 270):
            cx, cy = orig_w / 2.0, orig_h / 2.0
            rot_matrix = cv2.getRotationMatrix2D((cx, cy), -rotation, 1.0)
            cos_a, sin_a = abs(rot_matrix[0, 0]), abs(rot_matrix[0, 1])
            new_w = int(orig_w * cos_a + orig_h * sin_a)
            new_h = int(orig_w * sin_a + orig_h * cos_a)
            rot_matrix[0, 2] += (new_w - orig_w) / 2.0
            rot_matrix[1, 2] += (new_h - orig_h) / 2.0
            rotated_size = (new_w, new_h)

        rx, ry, rw, rh = params.cropbox
        fps = float(stream.average_rate) if stream.average_rate else params.fps
        time_base = stream.time_base

        if params.start_frame > 0 and time_base and fps > 0:
            target_sec = params.start_frame / fps
            target_pts = round(target_sec / time_base)
            container.seek(target_pts, stream=stream, backward=True)

        frames_written = 0
        frame_idx = 0
        for av_frame in container.decode(stream):
            runtime.raise_if_cancelled()

            if av_frame.pts is not None and time_base and fps > 0:
                current_sec = float(av_frame.pts * time_base)
                current_idx = round(current_sec * fps)
            else:
                current_idx = frame_idx

            if current_idx < params.start_frame:
                continue
            if current_idx >= params.end_frame:
                break

            frame = av_frame.to_ndarray(format="bgr24")
            frame = _rotate_frame(frame, rotation, rot_matrix, rotated_size)
            frame = frame[ry : ry + rh, rx : rx + rw]
            frame = cv2.resize(frame, (target_w, target_h))

            if rotate_180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)

            frame_path = os.path.join(
                temp_dir,
                f"frame_{frames_written:06d}.png",
            ).replace("\\", "/")
            success, encoded = cv2.imencode(".png", frame)
            if success:
                with open(frame_path, "wb") as file_obj:
                    file_obj.write(encoded.tobytes())
                frames_written += 1

            if frames_written and frames_written % 10 == 0:
                progress = base_progress + int(
                    (frames_written / max(total_frames, 1)) * 50 / total_tasks
                )
                runtime.emit_progress(
                    progress,
                    f"处理帧 {frames_written}/{total_frames}",
                )
            frame_idx += 1

        container.close()

        if frames_written == 0:
            raise RuntimeError("没有成功写入任何视频帧")

        expected_frames = params.end_frame - params.start_frame
        if frames_written < expected_frames * 0.9:
            logger.warning(
                "Frame count below expectation: expected %s, actual %s",
                expected_frames,
                frames_written,
            )

        runtime.emit_progress(base_progress + 50, "正在编码视频...")
        run_ffmpeg_crf(
            input_pattern=build_frame_pattern(temp_dir),
            output_file=output_path.replace("\\", "/"),
            fps=params.fps,
            padded_w=padded_w,
            padded_h=padded_h,
            runtime=runtime,
        )
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def run_ffmpeg_crf(
    *,
    input_pattern: str,
    output_file: str,
    fps: float,
    padded_w: int,
    padded_h: int,
    runtime: ProtectedExportRuntime,
) -> None:
    """Encode PNG frames to H.264 using CRF settings."""
    runtime.raise_if_cancelled()

    filters = []
    if padded_w > 0 and padded_h > 0:
        filters.append(f"pad={padded_w}:{padded_h}:0:0:black")

    cmd = [
        runtime.ffmpeg_path,
        "-hide_banner",
        "-framerate",
        str(fps),
        "-i",
        input_pattern,
    ]
    if filters:
        cmd.extend(["-vf", ",".join(filters)])
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "19",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-pix_fmt",
            "yuv420p",
            "-x264-params",
            X264_PARAMS,
            "-an",
            "-y",
            output_file,
        ]
    )

    popen_kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(cmd, **popen_kwargs)
    runtime.set_ffmpeg_process(process)

    stderr = ""
    try:
        while True:
            try:
                _stdout, stderr = process.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if runtime.is_cancelled():
                    process.kill()
                    process.communicate()
                    raise InterruptedError("导出已取消")
    finally:
        runtime.set_ffmpeg_process(None)

    if runtime.is_cancelled():
        raise InterruptedError("导出已取消")
    if process.returncode != 0:
        stderr_msg = stderr[-500:] if stderr else "未知错误"
        raise RuntimeError(
            f"ffmpeg CRF编码失败 (code {process.returncode}): {stderr_msg}"
        )


def export_video_from_image(
    *,
    output_path: str,
    params: Any,
    runtime: ProtectedExportRuntime,
    base_progress: int,
    total_tasks: int,
) -> None:
    """Generate a short video from one still image."""
    spec = get_resolution_spec(params.resolution)
    target_w = spec["width"]
    target_h = spec["height"]
    padded_w = spec["padded_width"]
    padded_h = spec["padded_height"]
    rotate_180 = spec["rotate_180"]

    image_array = np.fromfile(params.video_path, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError(f"无法打开图片: {params.video_path}")

    frame = cv2.resize(frame, (target_w, target_h))
    if rotate_180:
        frame = cv2.rotate(frame, cv2.ROTATE_180)

    temp_dir = os.path.join(runtime.output_dir, "_temp_frames").replace("\\", "/")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        fps = 30.0
        total_frames = 30

        for frame_idx in range(total_frames):
            runtime.raise_if_cancelled()
            frame_path = os.path.join(
                temp_dir,
                f"frame_{frame_idx:06d}.png",
            ).replace("\\", "/")
            success, encoded = cv2.imencode(".png", frame)
            if success:
                with open(frame_path, "wb") as file_obj:
                    file_obj.write(encoded.tobytes())

            if frame_idx % 10 == 0:
                progress = base_progress + int(
                    (frame_idx / total_frames) * 50 / total_tasks
                )
                runtime.emit_progress(
                    progress,
                    f"生成帧 {frame_idx}/{total_frames}",
                )

        runtime.emit_progress(base_progress + 50, "正在编码视频...")
        run_ffmpeg_crf(
            input_pattern=build_frame_pattern(temp_dir),
            output_file=output_path.replace("\\", "/"),
            fps=fps,
            padded_w=padded_w,
            padded_h=padded_h,
            runtime=runtime,
        )
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def _rotate_frame(
    frame: np.ndarray,
    rotation: int,
    rot_matrix: np.ndarray | None,
    rotated_size: tuple[int, int] | None,
) -> np.ndarray:
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if rotation != 0 and rot_matrix is not None and rotated_size is not None:
        return cv2.warpAffine(
            frame,
            rot_matrix,
            rotated_size,
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
    return frame
