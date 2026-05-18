from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import utils.file_utils
from gui.main_window import MainWindow

_QT_APP: QApplication | None = None


class _DummyButton:
    def __init__(self) -> None:
        self.enabled = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled


class _DummyStatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str) -> None:
        self.messages.append(message)


class _DummyVideoPreview:
    def __init__(self) -> None:
        self.video_path = "preview.mp4"

    def get_cropbox_in_rotated_space(self) -> tuple[int, int, int, int]:
        return (1, 2, 3, 4)

    def get_rotation(self) -> int:
        return 90


class _DummyConfig:
    def __init__(self, loop_file: str, *, is_image: bool) -> None:
        self.loop = SimpleNamespace(file=loop_file, is_image=is_image)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "uuid": "12345678-1234-1234-1234-1234567890ab",
            "name": "test",
            "description": "",
            "icon": "",
            "screen": "360x640",
            "loop": {
                "file": self.loop.file,
                "is_image": self.loop.is_image,
            },
            "intro": {"enabled": False, "file": "", "duration": 5000000},
            "transition_in": {"type": "none"},
            "transition_loop": {"type": "none"},
            "overlay": {"type": "none"},
        }

    def save_to_file(self, path: str) -> None:
        Path(path).write_text("{}", encoding="utf-8")


class _FakeMainWindow:
    def __init__(self, tmp_path: Path) -> None:
        simulator_dir = tmp_path / "simulator"
        simulator_dir.mkdir()
        (simulator_dir / "arknights_pass_simulator.exe").write_bytes(b"stub")
        (tmp_path / "project.json").write_text("{}", encoding="utf-8")
        (tmp_path / "loop.png").write_bytes(b"image")

        self._config = _DummyConfig("loop.png", is_image=True)
        self._project_path = str(tmp_path / "project.json")
        self._base_dir = str(tmp_path)
        self._app_dir = str(tmp_path)
        self._is_modified = False
        self._simulator_launch_pending = False
        self._simulator_prepare_thread = None
        self._simulator_proc = None
        self._simulator_check_count = 0

        self.status_bar = _DummyStatusBar()
        self.timeline = SimpleNamespace(btn_preview=_DummyButton())
        self.video_preview = _DummyVideoPreview()

        self.thread_calls: list[dict] = []
        self.launch_calls: list[dict] = []
        self.completed_callback = None
        self.failed_callback = None
        self.progress_callback = None

    def _update_title(self) -> None:
        pass

    def _build_simulator_loop_request(self, *, resolved_loop_path: str):
        return MainWindow._build_simulator_loop_request(
            self,
            resolved_loop_path=resolved_loop_path,
        )

    def _set_simulator_launch_busy(self, busy: bool, message: str = "") -> None:
        MainWindow._set_simulator_launch_busy(self, busy, message)

    def _start_material_service_thread(self, command: str, payload: dict, **kwargs):
        self.thread_calls.append(
            {
                "command": command,
                "payload": payload,
                "kwargs": kwargs,
            }
        )
        self.completed_callback = kwargs.get("on_completed")
        self.failed_callback = kwargs.get("on_failed")
        self.progress_callback = kwargs.get("on_progress")
        return "thread"

    def _launch_simulator_process(self, **kwargs) -> None:
        self.launch_calls.append(kwargs)


def test_on_simulator_image_loop_is_prepared_asynchronously(tmp_path: Path) -> None:
    window = _FakeMainWindow(tmp_path)

    MainWindow._on_simulator(window)

    assert window._simulator_launch_pending is True
    assert window.timeline.btn_preview.enabled is False
    assert len(window.thread_calls) == 1
    assert window.thread_calls[0]["command"] == "prepare_loop_image_video"
    assert window.thread_calls[0]["payload"]["config_output_path"] == "_sim_temp_config.json"
    assert window.launch_calls == []

    assert window.progress_callback is not None
    window.progress_callback(35, "Preparing")
    assert window.status_bar.messages[-1] == "Preparing (35%)"

    assert window.completed_callback is not None
    prepared_config_path = str(tmp_path / "_sim_temp_config.json")
    window.completed_callback({"config_path": prepared_config_path})

    assert window._simulator_launch_pending is False
    assert window.timeline.btn_preview.enabled is True
    assert window._simulator_prepare_thread is None
    assert window.launch_calls == [
        {
            "simulator_path": str(tmp_path / "simulator" / "arknights_pass_simulator.exe"),
            "config_for_simulator": prepared_config_path,
            "cropbox": (1, 2, 3, 4),
            "rotation": 90,
        }
    ]


def test_on_simulator_returns_early_when_prepare_is_pending(tmp_path: Path) -> None:
    window = _FakeMainWindow(tmp_path)
    window._simulator_launch_pending = True

    MainWindow._on_simulator(window)

    assert window.thread_calls == []
    assert window.launch_calls == []
    assert window.status_bar.messages[-1] == "Preparing simulator preview..."


def _get_qt_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def test_real_main_window_on_simulator_uses_async_prepare(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _get_qt_app()

    app_dir = tmp_path
    (app_dir / "config").mkdir()
    (app_dir / "config" / "user_settings.json").write_text(
        '{"auto_create_temp_project": false}',
        encoding="utf-8",
    )
    simulator_dir = app_dir / "simulator"
    simulator_dir.mkdir()
    (simulator_dir / "arknights_pass_simulator.exe").write_bytes(b"stub")

    project_path = tmp_path / "project.json"
    project_path.write_text("{}", encoding="utf-8")
    loop_path = tmp_path / "loop.png"
    loop_path.write_bytes(b"image")

    monkeypatch.setattr(utils.file_utils, "get_app_dir", lambda: str(app_dir))
    monkeypatch.setattr(MainWindow, "_check_first_run", lambda self: None)
    monkeypatch.setattr(MainWindow, "_check_update_on_startup", lambda self: None)
    monkeypatch.setattr(MainWindow, "_check_crash_recovery", lambda self: None)

    window = MainWindow()
    window._config = _DummyConfig("loop.png", is_image=True)
    window._project_path = str(project_path)
    window._base_dir = str(tmp_path)
    window._is_modified = False

    monkeypatch.setattr(
        window.video_preview,
        "get_cropbox_in_rotated_space",
        lambda: (10, 20, 30, 40),
    )
    monkeypatch.setattr(window.video_preview, "get_rotation", lambda: 180)
    window.video_preview.video_path = "preview.mp4"

    thread_calls: list[dict] = []
    launch_calls: list[dict] = []
    callbacks: dict[str, object] = {}

    def fake_start_material_service_thread(command: str, payload: dict, **kwargs):
        thread_calls.append(
            {
                "command": command,
                "payload": payload,
                "kwargs": kwargs,
            }
        )
        callbacks.update(kwargs)
        return "thread"

    def fake_launch_simulator_process(**kwargs) -> None:
        launch_calls.append(kwargs)

    monkeypatch.setattr(
        window,
        "_start_material_service_thread",
        fake_start_material_service_thread,
    )
    monkeypatch.setattr(
        window,
        "_launch_simulator_process",
        fake_launch_simulator_process,
    )

    window._on_simulator()

    assert window._simulator_launch_pending is True
    assert window.timeline.btn_preview.isEnabled() is False
    assert len(thread_calls) == 1
    assert thread_calls[0]["command"] == "prepare_loop_image_video"
    assert launch_calls == []

    progress = callbacks["on_progress"]
    assert callable(progress)
    progress(40, "Preparing")
    assert window.status_bar.currentMessage() == "Preparing (40%)"

    completed = callbacks["on_completed"]
    assert callable(completed)
    prepared_config_path = str(tmp_path / "_sim_temp_config.json")
    completed({"config_path": prepared_config_path})

    assert window._simulator_launch_pending is False
    assert window.timeline.btn_preview.isEnabled() is True
    assert launch_calls == [
        {
            "simulator_path": str(simulator_dir / "arknights_pass_simulator.exe"),
            "config_for_simulator": prepared_config_path,
            "cropbox": (10, 20, 30, 40),
            "rotation": 180,
        }
    ]

    window._material_service.close()
    window.deleteLater()
