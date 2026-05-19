"""Entry point for isolated export and validation operations."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any

try:
    import cv2
except ImportError:  # pragma: no cover - dependency probe
    cv2 = None

try:
    import av
except ImportError:  # pragma: no cover - dependency probe
    av = None

from config.constants import ARK_CLASS_ICON_SIZE, ARK_LOGO_SIZE
from config.epconfig import EPConfig, OverlayType
from core._protected.export_core import (
    ProtectedExportRuntime,
    execute_task,
    save_epconfig,
)
from core._protected.image_core import ImageProcessor
from core._protected.validator_core import EPConfigValidator
from core.export_models import MaterialExportRequest, VideoExportParams
from material_stdio_utils import configure_utf8_stdio

logger = logging.getLogger(__name__)


@dataclass
class WorkerTask:
    export_type: str
    output_path: str
    data: Any


def emit(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_progress(percent: int, message: str) -> None:
    emit({"type": "progress", "percent": int(percent), "message": message})


def fail(message: str, *, exit_code: int = 1) -> int:
    emit({"type": "failed", "message": message})
    return exit_code


def resolve_path(base_dir: str, path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def encode_validation_results(payload: dict[str, Any]) -> dict[str, Any]:
    validator = EPConfigValidator(payload.get("base_dir", ""))
    results = validator.validate(payload["config"])
    return {
        "type": "result",
        "results": [
            {
                "level": result.level.value,
                "field": result.field,
                "message": result.message,
            }
            for result in results
        ],
        "summary": validator.get_summary(),
    }


def maybe_probe_video_params(
    base_dir: str,
    relative_path: str,
    resolution: str,
) -> VideoExportParams | None:
    if av is None:
        return None
    absolute_path = resolve_path(base_dir, relative_path)
    if not absolute_path or not os.path.exists(absolute_path):
        return None

    container = av.open(absolute_path)
    try:
        stream = container.streams.video[0]
        fps = float(stream.average_rate) if stream.average_rate else 30.0
        total_frames = stream.frames
        if total_frames == 0 and stream.duration and stream.time_base:
            total_frames = max(
                1,
                int(float(stream.duration * stream.time_base) * fps),
            )
        if total_frames == 0:
            total_frames = 1
        return VideoExportParams(
            video_path=absolute_path,
            cropbox=(0, 0, int(stream.width), int(stream.height)),
            start_frame=0,
            end_frame=int(total_frames),
            fps=fps,
            resolution=resolution,
            rotation=0,
        )
    finally:
        container.close()


def build_export_tasks(request: MaterialExportRequest) -> list[WorkerTask]:
    tasks: list[WorkerTask] = []
    epconfig = EPConfig.from_dict(request.config)

    if request.icon_path:
        icon_path = resolve_path(request.base_dir, request.icon_path)
        if os.path.exists(icon_path):
            logo_image = ImageProcessor.load_image(icon_path)
            if logo_image is not None:
                tasks.append(
                    WorkerTask(
                        export_type="icon",
                        output_path="icon.png",
                        data=ImageProcessor.process_for_logo(logo_image),
                    )
                )

    if epconfig.overlay.type == OverlayType.IMAGE:
        image_options = epconfig.overlay.image_options
        if image_options and image_options.image:
            image_path = resolve_path(request.base_dir, image_options.image)
            if os.path.exists(image_path):
                overlay_image = ImageProcessor.load_image(image_path)
                if overlay_image is not None:
                    tasks.append(
                        WorkerTask(
                            export_type="overlay",
                            output_path="overlay.argb",
                            data=ImageProcessor.process_for_overlay(
                                overlay_image,
                                epconfig.screen.value,
                            ),
                        )
                    )

    if request.loop_image_path:
        tasks.append(
            WorkerTask(
                export_type="loop",
                output_path="loop.mp4",
                data=VideoExportParams(
                    video_path=resolve_path(request.base_dir, request.loop_image_path),
                    cropbox=(0, 0, 0, 0),
                    start_frame=0,
                    end_frame=30,
                    fps=30.0,
                    resolution=epconfig.screen.value,
                    is_image=True,
                ),
            )
        )
    elif request.loop_video_params is not None:
        request.loop_video_params.resolution = epconfig.screen.value
        request.loop_video_params.video_path = resolve_path(
            request.base_dir,
            request.loop_video_params.video_path,
        )
        tasks.append(
            WorkerTask(
                export_type="loop",
                output_path="loop.mp4",
                data=request.loop_video_params,
            )
        )

    intro_params = request.intro_video_params
    if intro_params is None and epconfig.intro.enabled and epconfig.intro.file:
        intro_params = maybe_probe_video_params(
            request.base_dir,
            epconfig.intro.file,
            epconfig.screen.value,
        )
    if intro_params is not None:
        intro_params.resolution = epconfig.screen.value
        intro_params.video_path = resolve_path(request.base_dir, intro_params.video_path)
        tasks.append(
            WorkerTask(
                export_type="intro",
                output_path="intro.mp4",
                data=intro_params,
            )
        )

    return tasks


def copy_png_variant(
    *,
    source_path: str,
    output_path: str,
    target_size: tuple[int, int],
) -> None:
    if cv2 is None or not source_path or not os.path.exists(source_path):
        return
    image = ImageProcessor.load_image(source_path)
    if image is None:
        return
    image = cv2.resize(image, target_size)
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError(f"Failed to encode image: {source_path}")
    with open(output_path, "wb") as file_obj:
        file_obj.write(encoded.tobytes())


def export_extra_assets(request: MaterialExportRequest) -> None:
    epconfig = EPConfig.from_dict(request.config)

    if epconfig.overlay.type == OverlayType.IMAGE:
        image_options = epconfig.overlay.image_options
        if image_options and image_options.image:
            source_path = resolve_path(request.base_dir, image_options.image)
            if os.path.exists(source_path):
                shutil.copyfile(
                    source_path,
                    os.path.join(request.output_dir, "overlay.png"),
                )

    if epconfig.overlay.type != OverlayType.ARKNIGHTS:
        return

    ark_options = epconfig.overlay.arknights_options
    if ark_options is None:
        return

    if ark_options.operator_class_icon:
        copy_png_variant(
            source_path=resolve_path(request.base_dir, ark_options.operator_class_icon),
            output_path=os.path.join(request.output_dir, "class_icon.png"),
            target_size=ARK_CLASS_ICON_SIZE,
        )

    if ark_options.logo:
        copy_png_variant(
            source_path=resolve_path(request.base_dir, ark_options.logo),
            output_path=os.path.join(request.output_dir, "ark_logo.png"),
            target_size=ARK_LOGO_SIZE,
        )


def handle_export(payload: dict[str, Any]) -> int:
    request = MaterialExportRequest.from_dict(payload)
    ffmpeg_path = str(payload.get("ffmpeg_path", ""))
    tasks = build_export_tasks(request)

    if request.requires_ffmpeg() and not ffmpeg_path:
        return fail("FFmpeg is required for video export")

    os.makedirs(request.output_dir, exist_ok=True)
    runtime = ProtectedExportRuntime(
        ffmpeg_path=ffmpeg_path,
        output_dir=request.output_dir,
        progress_callback=emit_progress,
        cancel_check=lambda: False,
    )

    total_tasks = len(tasks)
    if total_tasks == 0:
        emit_progress(90, "Writing project metadata...")
    for index, task in enumerate(tasks):
        execute_task(
            export_type=task.export_type,
            output_path=os.path.join(request.output_dir, task.output_path),
            data=task.data,
            runtime=runtime,
            base_progress=int((index / (total_tasks + 1)) * 100),
            total_tasks=max(total_tasks, 1),
            task_label=task.output_path,
        )

    export_extra_assets(request)

    epconfig = EPConfig.from_dict(request.config)
    config_path = os.path.join(request.output_dir, "epconfig.json")
    save_epconfig(config_path, epconfig.to_dict(normalize_paths=True))

    emit_progress(100, "Export completed")
    emit(
        {
            "type": "completed",
            "message": f"Export completed: {request.output_dir}",
        }
    )
    return 0


def main() -> int:
    configure_utf8_stdio()
    logging.basicConfig(level=logging.ERROR)

    request_line = sys.stdin.readline()
    if not request_line:
        return fail("Worker received no request")

    try:
        request = json.loads(request_line)
        command = request["command"]
        payload = request.get("payload", {})
        if command == "validate":
            emit(encode_validation_results(payload))
            return 0
        if command == "export":
            return handle_export(payload)
        return fail(f"Unsupported worker command: {command}")
    except Exception as exc:  # pragma: no cover - top-level safety
        logger.exception("Material worker failed")
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
