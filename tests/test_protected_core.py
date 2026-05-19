import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from build import SERVICE_EXE_NAME, WORKER_EXE_NAME, audit_protection_layout
from core._protected.export_core import (
    ProtectedExportRuntime,
    build_frame_pattern,
    execute_task,
    save_epconfig,
    write_argb,
)
from core.export_models import LoopImageVideoRequest, MaterialExportBuildRequest, TransitionCropRequest, VideoSelection
from core.image_processor import ImageProcessor
from core.material_service_client import MaterialServiceClient
from core.material_worker_client import run_worker_validation, spawn_worker_process
from core.export_service import ExportService, VideoExportParams
from core.overlay_renderer import OverlayRenderer
from core.video_processor import VideoProcessor
from protected_worker.service_main import emit as emit_service_message
from protected_worker.stdio_utils import configure_utf8_stdio
from protected_worker.worker_main import emit as emit_worker_message


def test_write_argb_rotates_and_writes_bgra(tmp_path: Path) -> None:
    frame = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)
    output = tmp_path / "overlay.argb"

    write_argb(str(output), frame, lambda: False)

    assert output.read_bytes() == bytes([10, 20, 30, 40])


def test_save_epconfig_preserves_utf8(tmp_path: Path) -> None:
    output = tmp_path / "epconfig.json"

    save_epconfig(str(output), {"name": "素材制作"})

    assert "素材制作" in output.read_text(encoding="utf-8")


def test_build_frame_pattern_uses_posix_separator() -> None:
    assert build_frame_pattern(r"C:\temp\frames").endswith(
        "C:/temp/frames/frame_%06d.png"
    )


def test_execute_task_writes_overlay_and_reports_progress(tmp_path: Path) -> None:
    progress_events: list[tuple[int, str]] = []
    runtime = ProtectedExportRuntime(
        ffmpeg_path="",
        output_dir=str(tmp_path),
        progress_callback=lambda percent, message: progress_events.append(
            (percent, message)
        ),
        cancel_check=lambda: False,
    )
    frame = np.array([[[10, 20, 30, 40]]], dtype=np.uint8)
    output = tmp_path / "overlay.argb"

    execute_task(
        export_type="overlay",
        output_path=str(output),
        data=frame,
        runtime=runtime,
        base_progress=12,
        total_tasks=1,
        task_label="overlay.argb",
    )

    assert output.read_bytes() == bytes([10, 20, 30, 40])
    assert progress_events[0][0] == 12
    assert "overlay.argb" in progress_events[0][1]


def test_execute_task_checks_cancellation_before_work(tmp_path: Path) -> None:
    runtime = ProtectedExportRuntime(
        ffmpeg_path="",
        output_dir=str(tmp_path),
        progress_callback=lambda _percent, _message: None,
        cancel_check=lambda: True,
    )

    with pytest.raises(InterruptedError):
        execute_task(
            export_type="overlay",
            output_path=str(tmp_path / "overlay.argb"),
            data=np.zeros((1, 1, 4), dtype=np.uint8),
            runtime=runtime,
            base_progress=0,
            total_tasks=1,
            task_label="overlay.argb",
        )


def test_runtime_cancel_terminates_active_process(tmp_path: Path) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

    fake_process = FakeProcess()
    runtime = ProtectedExportRuntime(
        ffmpeg_path="ffmpeg",
        output_dir=str(tmp_path),
        progress_callback=lambda _percent, _message: None,
        cancel_check=lambda: False,
    )

    runtime.set_ffmpeg_process(fake_process)  # type: ignore[arg-type]
    runtime.cancel()

    assert fake_process.terminated is True


def test_export_service_facade_stays_thin() -> None:
    facade_source = Path("core/export_service.py").read_text(encoding="utf-8")

    assert "ProtectedExportRuntime" not in facade_source
    assert "execute_task(" not in facade_source
    assert "import cv2" not in facade_source
    assert "import av" not in facade_source
    assert "spawn_worker_process" in facade_source


def test_public_facades_still_export_expected_types() -> None:
    assert ExportService.__name__ == "ExportService"
    assert VideoExportParams.__name__ == "VideoExportParams"
    assert OverlayRenderer.__name__ == "OverlayRenderer"
    assert VideoProcessor.__name__ == "VideoProcessor"


def test_runtime_package_no_longer_contains_protected_sources() -> None:
    protected_dir = Path("core/_protected")

    leaked_sources = [
        path.name
        for path in protected_dir.glob("*.py")
        if path.name != "__init__.py"
    ]

    assert leaked_sources == []


def test_build_audit_rejects_leaked_worker_package(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    build_root = tmp_path / "build"
    (project_root / "core" / "_protected").mkdir(parents=True)
    (project_root / "core" / "_protected" / "__init__.py").write_text("", encoding="utf-8")
    (build_root / "lib" / "protected_worker").mkdir(parents=True)
    (build_root / WORKER_EXE_NAME).write_bytes(b"worker")
    (build_root / SERVICE_EXE_NAME).write_bytes(b"service")

    with pytest.raises(RuntimeError, match="protected_worker package"):
        audit_protection_layout(str(project_root), str(build_root))


def test_build_audit_requires_worker_executable(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    build_root = tmp_path / "build"
    (project_root / "core" / "_protected").mkdir(parents=True)
    (project_root / "core" / "_protected" / "__init__.py").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match=WORKER_EXE_NAME):
        audit_protection_layout(str(project_root), str(build_root))


def test_build_audit_requires_service_executable(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    build_root = tmp_path / "build"
    (project_root / "core" / "_protected").mkdir(parents=True)
    (project_root / "core" / "_protected" / "__init__.py").write_text("", encoding="utf-8")
    build_root.mkdir()
    (build_root / WORKER_EXE_NAME).write_bytes(b"worker")

    with pytest.raises(RuntimeError, match=SERVICE_EXE_NAME):
        audit_protection_layout(str(project_root), str(build_root))


def test_material_service_crops_transition_image(tmp_path: Path) -> None:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[1:3, 1:3] = 255
    source_path = tmp_path / "trans_in_src.png"
    assert ImageProcessor.save_image(image, str(source_path)) is True

    client = MaterialServiceClient()
    try:
        result = client.request(
            "crop_transition_image",
            TransitionCropRequest(
                base_dir=str(tmp_path),
                trans_type="in",
                cropbox=(1, 1, 2, 2),
                target_resolution=(3, 5),
            ).to_dict(),
        )
    finally:
        client.close()

    output_path = Path(result["output_path"])
    assert output_path.exists()
    cropped = ImageProcessor.load_image(str(output_path))
    assert cropped is not None
    assert cropped.shape[:2] == (5, 3)


def test_material_service_captures_icon_from_image(tmp_path: Path) -> None:
    image = np.zeros((6, 6, 3), dtype=np.uint8)
    image[2:5, 2:5] = 200
    source_path = tmp_path / "icon_source.png"
    assert ImageProcessor.save_image(image, str(source_path)) is True

    client = MaterialServiceClient()
    try:
        result = client.request(
            "capture_icon",
            {
                "base_dir": str(tmp_path),
                "source_type": "image",
                "source_path": "icon_source.png",
                "output_path": "icon.png",
                "cropbox": [2, 2, 3, 3],
                "rotation": 0,
                "frame_index": 0,
            },
        )
    finally:
        client.close()

    output_path = Path(result["output_path"])
    assert output_path.exists()
    icon = ImageProcessor.load_image(str(output_path))
    assert icon is not None
    assert icon.shape[:2] == (3, 3)


def test_material_service_builds_export_request(tmp_path: Path) -> None:
    client = MaterialServiceClient()
    try:
        result = client.request(
            "build_export_request",
            MaterialExportBuildRequest(
                base_dir=str(tmp_path),
                config={
                    "version": 1,
                    "uuid": "12345678-1234-1234-1234-1234567890ab",
                    "name": "service",
                    "description": "",
                    "icon": "icon.png",
                    "screen": "360x640",
                    "loop": {"file": "loop.mp4", "is_image": False},
                    "intro": {"enabled": False, "file": "", "duration": 5000000},
                    "transition_in": {"type": "none"},
                    "transition_loop": {"type": "none"},
                    "overlay": {"type": "none"},
                },
                icon_path="icon.png",
                loop_video_selection=VideoSelection(
                    video_path="loop-source.mp4",
                    cropbox=(1, 2, 3, 4),
                    start_frame=5,
                    end_frame=25,
                    fps=30.0,
                    rotation=90,
                ),
            ).to_dict(),
        )
    finally:
        client.close()

    assert result["icon_path"] == "icon.png"
    assert result["loop_video_params"]["cropbox"] == [1, 2, 3, 4]
    assert result["loop_video_params"]["rotation"] == 90
    assert result["loop_image_path"] == ""


def test_material_service_prepares_loop_image_video(tmp_path: Path) -> None:
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :] = [0, 128, 255]
    source_path = tmp_path / "loop.png"
    assert ImageProcessor.save_image(image, str(source_path)) is True

    client = MaterialServiceClient()
    try:
        result = client.request(
            "prepare_loop_image_video",
            LoopImageVideoRequest(
                base_dir=str(tmp_path),
                image_path="loop.png",
                output_path="_sim_temp.mp4",
                resolution="360x640",
                fps=30.0,
                frame_count=5,
                config={
                    "version": 1,
                    "uuid": "12345678-1234-1234-1234-1234567890ab",
                    "name": "sim",
                    "description": "",
                    "icon": "",
                    "screen": "360x640",
                    "loop": {"file": "loop.png", "is_image": True},
                    "intro": {"enabled": False, "file": "", "duration": 5000000},
                    "transition_in": {"type": "none"},
                    "transition_loop": {"type": "none"},
                    "overlay": {"type": "none"},
                },
                config_output_path="_sim_temp_config.json",
            ).to_dict(),
        )
    finally:
        client.close()

    assert (tmp_path / "_sim_temp.mp4").exists()
    config_path = Path(result["config_path"])
    assert config_path.exists()
    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_data["loop"]["file"] == "_sim_temp.mp4"
    assert config_data["loop"]["is_image"] is False


def test_worker_validation_returns_serialized_results() -> None:
    results = run_worker_validation(
        {
            "version": 2,
            "uuid": "not-a-uuid",
            "screen": "invalid",
            "loop": {"file": ""},
        }
    )

    fields = {result["field"] for result in results}
    assert {"version", "uuid", "screen", "loop.file"} <= fields


def test_worker_export_writes_icon_and_epconfig(tmp_path: Path) -> None:
    icon_source = tmp_path / "source.png"
    icon_image = np.zeros((8, 8, 3), dtype=np.uint8)
    assert ImageProcessor.save_image(icon_image, str(icon_source)) is True

    request = {
        "command": "export",
        "payload": {
            "base_dir": str(tmp_path),
            "output_dir": str(tmp_path / "out"),
            "config": {
                "version": 1,
                "uuid": "12345678-1234-1234-1234-1234567890ab",
                "name": "worker",
                "description": "",
                "icon": "source.png",
                "screen": "360x640",
                "loop": {"file": "", "is_image": False},
                "intro": {"enabled": False, "file": "", "duration": 5000000},
                "transition_in": {"type": "none"},
                "transition_loop": {"type": "none"},
                "overlay": {"type": "none"},
            },
            "icon_path": "source.png",
            "loop_image_path": "",
            "loop_video_params": None,
            "intro_video_params": None,
            "ffmpeg_path": "",
        },
    }

    process = spawn_worker_process()
    assert process.stdin is not None
    assert process.stdout is not None
    stdout, stderr = process.communicate(f"{json.dumps(request)}\n")

    assert process.returncode == 0, stderr
    assert (tmp_path / "out" / "icon.png").exists()
    assert (tmp_path / "out" / "epconfig.json").exists()
    assert '"type": "completed"' in stdout


def test_worker_emit_uses_utf8_after_stdio_configuration(monkeypatch) -> None:
    stdout_buffer = io.BytesIO()
    stderr_buffer = io.BytesIO()
    monkeypatch.setattr(
        sys,
        "stdout",
        io.TextIOWrapper(stdout_buffer, encoding="cp1252"),
    )
    monkeypatch.setattr(
        sys,
        "stderr",
        io.TextIOWrapper(stderr_buffer, encoding="cp1252"),
    )

    configure_utf8_stdio()
    emit_worker_message({"type": "progress", "message": "正在导出 素材"})

    assert "正在导出 素材" in stdout_buffer.getvalue().decode("utf-8")


def test_service_emit_uses_utf8_after_stdio_configuration(monkeypatch) -> None:
    stdout_buffer = io.BytesIO()
    stderr_buffer = io.BytesIO()
    monkeypatch.setattr(
        sys,
        "stdout",
        io.TextIOWrapper(stdout_buffer, encoding="cp1252"),
    )
    monkeypatch.setattr(
        sys,
        "stderr",
        io.TextIOWrapper(stderr_buffer, encoding="cp1252"),
    )

    configure_utf8_stdio()
    emit_service_message("1", "progress", message="循环视频已准备", percent=85)

    assert "循环视频已准备" in stdout_buffer.getvalue().decode("utf-8")
