"""Entry point for the persistent material-service subprocess."""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
from fractions import Fraction
from typing import Any

try:
    import cv2
except ImportError:  # pragma: no cover - dependency probe
    cv2 = None

try:
    import av
except ImportError:  # pragma: no cover - dependency probe
    av = None

from config.constants import get_resolution_spec
from config.epconfig import EPConfig
from core._protected.image_core import ImageProcessor
from core.export_models import (
    IconCaptureRequest,
    LoopImageVideoRequest,
    MaterialExportBuildRequest,
    TransitionCropRequest,
    VideoExportParams,
    VideoProbeResult,
    VideoSelection,
)
from protected_worker.stdio_utils import configure_utf8_stdio

logger = logging.getLogger(__name__)


def emit(request_id: str, message_type: str, **fields: Any) -> None:
    message = {
        "request_id": request_id,
        "type": message_type,
        **fields,
    }
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_result(request_id: str, payload: dict[str, Any]) -> None:
    emit(request_id, "result", payload=payload)


def emit_progress(request_id: str, percent: int, message: str) -> None:
    emit(
        request_id,
        "progress",
        percent=int(percent),
        message=message,
    )


def fail(request_id: str, message: str) -> None:
    emit(request_id, "failed", message=message)


def resolve_path(base_dir: str, path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def path_for_config(base_dir: str, path: str) -> str:
    try:
        relative = os.path.relpath(path, base_dir)
    except ValueError:
        return path
    if relative.startswith(".."):
        return path
    return relative.replace("\\", "/")


def clamp_cropbox(
    cropbox: tuple[int, int, int, int],
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int]:
    x, y, w, h = cropbox
    x = max(0, min(int(x), frame_width - 1))
    y = max(0, min(int(y), frame_height - 1))
    w = min(int(w), frame_width - x)
    h = min(int(h), frame_height - y)
    return x, y, w, h


def apply_rotation_to_frame(frame, rotation: int):
    if cv2 is None or rotation == 0:
        return frame
    if rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

    height, width = frame.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), -rotation, 1.0)
    cos_a = abs(matrix[0, 0])
    sin_a = abs(matrix[0, 1])
    new_width = int(width * cos_a + height * sin_a)
    new_height = int(width * sin_a + height * cos_a)
    matrix[0, 2] += (new_width - width) / 2.0
    matrix[1, 2] += (new_height - height) / 2.0
    channels = frame.shape[2] if len(frame.shape) == 3 else 1
    if channels == 4:
        border_value = (0, 0, 0, 0)
    elif channels == 3:
        border_value = (0, 0, 0)
    else:
        border_value = 0
    return cv2.warpAffine(
        frame,
        matrix,
        (new_width, new_height),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )


def to_bgr_frame(frame):
    if cv2 is None:
        return frame
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def probe_video(base_dir: str, path: str) -> VideoProbeResult:
    if av is None:
        raise RuntimeError("PyAV is required for video probing")

    absolute_path = resolve_path(base_dir, path)
    if not absolute_path or not os.path.exists(absolute_path):
        raise FileNotFoundError(f"Video file not found: {path}")

    container = av.open(absolute_path)
    try:
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else 30.0
        total_frames = int(stream.frames or 0)
        if total_frames == 0 and stream.duration and stream.time_base:
            total_frames = max(
                1,
                int(float(stream.duration * stream.time_base) * fps),
            )
        if total_frames == 0:
            total_frames = 1
        return VideoProbeResult(
            video_path=absolute_path,
            width=int(stream.width),
            height=int(stream.height),
            total_frames=total_frames,
            fps=fps,
        )
    finally:
        container.close()


def build_video_export_params(
    selection: VideoSelection,
    *,
    base_dir: str,
    resolution: str,
) -> VideoExportParams:
    return VideoExportParams(
        video_path=resolve_path(base_dir, selection.video_path),
        cropbox=selection.cropbox,
        start_frame=selection.start_frame,
        end_frame=selection.end_frame,
        fps=selection.fps,
        resolution=resolution,
        rotation=selection.rotation,
    )


def handle_probe_video(payload: dict[str, Any]) -> dict[str, Any]:
    result = probe_video(str(payload.get("base_dir", "")), str(payload["path"]))
    return result.to_dict()


def handle_build_export_request(payload: dict[str, Any]) -> dict[str, Any]:
    request = MaterialExportBuildRequest.from_dict(payload)
    epconfig = EPConfig.from_dict(request.config)
    resolution = epconfig.screen.value

    result: dict[str, Any] = {
        "icon_path": request.icon_path or epconfig.icon,
        "loop_image_path": "",
        "loop_video_params": None,
        "intro_video_params": None,
    }

    if epconfig.loop.is_image:
        result["loop_image_path"] = request.loop_image_path or epconfig.loop.file
    elif request.loop_video_selection is not None:
        result["loop_video_params"] = build_video_export_params(
            request.loop_video_selection,
            base_dir=request.base_dir,
            resolution=resolution,
        ).to_dict()

    if epconfig.intro.enabled and epconfig.intro.file:
        if request.intro_video_selection is not None:
            result["intro_video_params"] = build_video_export_params(
                request.intro_video_selection,
                base_dir=request.base_dir,
                resolution=resolution,
            ).to_dict()
        else:
            try:
                intro_probe = probe_video(request.base_dir, epconfig.intro.file)
            except Exception:
                intro_probe = None
            if intro_probe is not None:
                result["intro_video_params"] = VideoExportParams(
                    video_path=intro_probe.video_path,
                    cropbox=(0, 0, intro_probe.width, intro_probe.height),
                    start_frame=0,
                    end_frame=intro_probe.total_frames,
                    fps=float(intro_probe.fps),
                    resolution=resolution,
                    rotation=0,
                ).to_dict()

    return result


def handle_crop_transition_image(payload: dict[str, Any]) -> dict[str, Any]:
    if cv2 is None:
        raise RuntimeError("OpenCV is required for transition cropping")

    request = TransitionCropRequest.from_dict(payload)
    pattern = os.path.join(request.base_dir, f"trans_{request.trans_type}_src.*")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(
            f"Transition source image not found for type: {request.trans_type}"
        )

    source_path = matches[0]
    original = cv2.imread(source_path, cv2.IMREAD_UNCHANGED)
    if original is None:
        raise RuntimeError(f"Failed to load transition source image: {source_path}")

    frame_height, frame_width = original.shape[:2]
    x, y, w, h = clamp_cropbox(request.cropbox, frame_width, frame_height)
    if w <= 0 or h <= 0:
        raise RuntimeError("Transition cropbox is invalid")

    cropped = original[y : y + h, x : x + w]
    target_width, target_height = request.target_resolution
    resized = cv2.resize(
        cropped,
        (target_width, target_height),
        interpolation=cv2.INTER_AREA,
    )

    output_path = os.path.join(
        request.base_dir,
        f"trans_{request.trans_type}_image.png",
    )
    success, encoded = cv2.imencode(".png", resized)
    if not success:
        raise RuntimeError(f"Failed to encode transition image: {source_path}")
    with open(output_path, "wb") as file_obj:
        file_obj.write(encoded.tobytes())

    return {
        "output_path": output_path,
        "source_path": source_path,
    }


def load_source_frame(request: IconCaptureRequest):
    if request.source_type == "image":
        source_path = resolve_path(request.base_dir, request.source_path)
        image = ImageProcessor.load_image(source_path)
        if image is None:
            raise RuntimeError(f"Failed to load icon source image: {source_path}")
        return image

    if request.source_type != "video":
        raise RuntimeError(f"Unsupported icon source type: {request.source_type}")

    if av is None:
        raise RuntimeError("PyAV is required for video-backed icon capture")

    source_path = resolve_path(request.base_dir, request.source_path)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Icon source video not found: {source_path}")

    container = av.open(source_path)
    try:
        for index, frame in enumerate(container.decode(video=0)):
            if index == request.frame_index:
                return frame.to_ndarray(format="bgr24")
    finally:
        container.close()

    raise RuntimeError(
        f"Unable to decode frame {request.frame_index} from video: {source_path}"
    )


def handle_capture_icon(payload: dict[str, Any]) -> dict[str, Any]:
    if cv2 is None:
        raise RuntimeError("OpenCV is required for icon capture")

    request = IconCaptureRequest.from_dict(payload)
    frame = load_source_frame(request)
    frame = apply_rotation_to_frame(frame, request.rotation)

    frame_height, frame_width = frame.shape[:2]
    x, y, w, h = clamp_cropbox(request.cropbox, frame_width, frame_height)
    if w <= 0 or h <= 0:
        raise RuntimeError("Icon cropbox is invalid")

    cropped = frame[y : y + h, x : x + w]
    output_path = resolve_path(request.base_dir, request.output_path)
    success, encoded = cv2.imencode(".png", cropped)
    if not success:
        raise RuntimeError(f"Failed to encode icon image: {output_path}")
    with open(output_path, "wb") as file_obj:
        file_obj.write(encoded.tobytes())

    return {
        "output_path": output_path,
        "relative_output_path": path_for_config(request.base_dir, output_path),
    }


def write_loop_image_video(
    *,
    image_path: str,
    output_path: str,
    resolution: str,
    fps: float,
    frame_count: int,
) -> None:
    if av is None or cv2 is None:
        raise RuntimeError("PyAV and OpenCV are required for loop-image rendering")

    image = ImageProcessor.load_image(image_path)
    if image is None:
        raise RuntimeError(f"Failed to load loop image: {image_path}")

    spec = get_resolution_spec(resolution)
    frame_bgr = cv2.resize(to_bgr_frame(image), (spec["width"], spec["height"]))
    rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    container = av.open(output_path, mode="w")
    try:
        normalized_fps = fps if fps > 0 else 30.0
        stream = container.add_stream(
            "libx264",
            rate=Fraction(str(normalized_fps)).limit_denominator(1000),
        )
        stream.width = spec["width"]
        stream.height = spec["height"]
        stream.pix_fmt = "yuv420p"
        for _ in range(frame_count):
            av_frame = av.VideoFrame.from_ndarray(rgb_frame, format="rgb24")
            for packet in stream.encode(av_frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    finally:
        container.close()


def handle_prepare_loop_image_video(
    payload: dict[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    request = LoopImageVideoRequest.from_dict(payload)
    image_path = resolve_path(request.base_dir, request.image_path)
    output_path = resolve_path(request.base_dir, request.output_path)

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Loop image not found: {image_path}")

    emit_progress(request_id, 20, "Loading loop image...")
    write_loop_image_video(
        image_path=image_path,
        output_path=output_path,
        resolution=request.resolution,
        fps=request.fps,
        frame_count=request.frame_count,
    )
    emit_progress(request_id, 85, "Loop video rendered")

    config_path = ""
    if request.config is not None and request.config_output_path:
        config = EPConfig.from_dict(request.config)
        config.loop.file = path_for_config(request.base_dir, output_path)
        config.loop.is_image = False
        config_path = resolve_path(request.base_dir, request.config_output_path)
        config_data = config.to_dict()
        loop_data = dict(config_data.get("loop") or {})
        loop_data["file"] = config.loop.file
        loop_data["is_image"] = False
        config_data["loop"] = loop_data
        output_dir = os.path.dirname(config_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as file_obj:
            json.dump(config_data, file_obj, ensure_ascii=False, indent=4)

    emit_progress(request_id, 100, "Loop image video ready")
    return {
        "video_path": output_path,
        "config_path": config_path,
    }


def handle_request(request_id: str, command: str, payload: dict[str, Any]) -> bool:
    if command == "shutdown":
        emit_result(request_id, {"message": "material service stopped"})
        return False
    if command == "probe_video":
        emit_result(request_id, handle_probe_video(payload))
        return True
    if command == "build_export_request":
        emit_result(request_id, handle_build_export_request(payload))
        return True
    if command == "crop_transition_image":
        emit_result(request_id, handle_crop_transition_image(payload))
        return True
    if command == "capture_icon":
        emit_result(request_id, handle_capture_icon(payload))
        return True
    if command == "prepare_loop_image_video":
        emit_result(
            request_id,
            handle_prepare_loop_image_video(payload, request_id=request_id),
        )
        return True

    fail(request_id, f"Unsupported service command: {command}")
    return True


def main() -> int:
    configure_utf8_stdio()
    logging.basicConfig(level=logging.ERROR)

    while True:
        request_line = sys.stdin.readline()
        if not request_line:
            return 0

        try:
            request = json.loads(request_line)
            request_id = str(request.get("request_id", ""))
            command = str(request["command"])
            payload = request.get("payload", {})
            if not request_id:
                raise RuntimeError("Service request is missing request_id")
            should_continue = handle_request(request_id, command, payload)
            if not should_continue:
                return 0
        except Exception as exc:  # pragma: no cover - top-level safety
            request_id = ""
            try:
                request_id = str(request.get("request_id", ""))
            except Exception:
                pass
            logger.exception("Material service failed")
            fail(request_id or "unknown", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
