"""Shared export request models used by the GUI and the worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VideoSelection:
    """High-level video selection payload captured from the GUI state."""

    video_path: str
    cropbox: tuple[int, int, int, int]
    start_frame: int
    end_frame: int
    fps: float
    rotation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "cropbox": list(self.cropbox),
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "fps": self.fps,
            "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoSelection":
        return cls(
            video_path=str(data["video_path"]),
            cropbox=tuple(int(value) for value in data["cropbox"]),
            start_frame=int(data["start_frame"]),
            end_frame=int(data["end_frame"]),
            fps=float(data["fps"]),
            rotation=int(data.get("rotation", 0)),
        )


@dataclass
class VideoExportParams:
    """Video export parameters passed to the protected worker."""

    video_path: str
    cropbox: tuple[int, int, int, int]
    start_frame: int
    end_frame: int
    fps: float
    resolution: str = "360x640"
    is_image: bool = False
    rotation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "cropbox": list(self.cropbox),
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "fps": self.fps,
            "resolution": self.resolution,
            "is_image": self.is_image,
            "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoExportParams":
        return cls(
            video_path=str(data["video_path"]),
            cropbox=tuple(int(value) for value in data["cropbox"]),
            start_frame=int(data["start_frame"]),
            end_frame=int(data["end_frame"]),
            fps=float(data["fps"]),
            resolution=str(data.get("resolution", "360x640")),
            is_image=bool(data.get("is_image", False)),
            rotation=int(data.get("rotation", 0)),
        )


@dataclass
class VideoProbeResult:
    """Serializable video metadata returned by the persistent service."""

    video_path: str
    width: int
    height: int
    total_frames: int
    fps: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "width": self.width,
            "height": self.height,
            "total_frames": self.total_frames,
            "fps": self.fps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoProbeResult":
        return cls(
            video_path=str(data["video_path"]),
            width=int(data["width"]),
            height=int(data["height"]),
            total_frames=int(data["total_frames"]),
            fps=float(data["fps"]),
        )


@dataclass
class TransitionCropRequest:
    """Crop-and-resize request for a transition image asset."""

    base_dir: str
    trans_type: str
    cropbox: tuple[int, int, int, int]
    target_resolution: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_dir": self.base_dir,
            "trans_type": self.trans_type,
            "cropbox": list(self.cropbox),
            "target_resolution": list(self.target_resolution),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionCropRequest":
        return cls(
            base_dir=str(data["base_dir"]),
            trans_type=str(data["trans_type"]),
            cropbox=tuple(int(value) for value in data["cropbox"]),
            target_resolution=tuple(
                int(value) for value in data["target_resolution"]
            ),
        )


@dataclass
class IconCaptureRequest:
    """Serializable request for saving a cropped icon asset."""

    base_dir: str
    source_type: str
    source_path: str
    output_path: str
    cropbox: tuple[int, int, int, int]
    rotation: int = 0
    frame_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_dir": self.base_dir,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "cropbox": list(self.cropbox),
            "rotation": self.rotation,
            "frame_index": self.frame_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IconCaptureRequest":
        return cls(
            base_dir=str(data["base_dir"]),
            source_type=str(data["source_type"]),
            source_path=str(data["source_path"]),
            output_path=str(data["output_path"]),
            cropbox=tuple(int(value) for value in data["cropbox"]),
            rotation=int(data.get("rotation", 0)),
            frame_index=int(data.get("frame_index", 0)),
        )


@dataclass
class LoopImageVideoRequest:
    """Serializable request for rendering an image-backed loop video."""

    base_dir: str
    image_path: str
    output_path: str
    resolution: str = "360x640"
    fps: float = 30.0
    frame_count: int = 30
    config: dict[str, Any] | None = None
    config_output_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_dir": self.base_dir,
            "image_path": self.image_path,
            "output_path": self.output_path,
            "resolution": self.resolution,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "config": self.config,
            "config_output_path": self.config_output_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopImageVideoRequest":
        return cls(
            base_dir=str(data["base_dir"]),
            image_path=str(data["image_path"]),
            output_path=str(data["output_path"]),
            resolution=str(data.get("resolution", "360x640")),
            fps=float(data.get("fps", 30.0)),
            frame_count=int(data.get("frame_count", 30)),
            config=(
                dict(data["config"])
                if isinstance(data.get("config"), dict)
                else None
            ),
            config_output_path=str(data.get("config_output_path", "")),
        )


@dataclass
class MaterialExportBuildRequest:
    """Serializable high-level export payload built from GUI state."""

    base_dir: str
    config: dict[str, Any]
    icon_path: str = ""
    loop_image_path: str = ""
    loop_video_selection: VideoSelection | None = None
    intro_video_selection: VideoSelection | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_dir": self.base_dir,
            "config": self.config,
            "icon_path": self.icon_path,
            "loop_image_path": self.loop_image_path,
            "loop_video_selection": (
                self.loop_video_selection.to_dict()
                if self.loop_video_selection is not None
                else None
            ),
            "intro_video_selection": (
                self.intro_video_selection.to_dict()
                if self.intro_video_selection is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialExportBuildRequest":
        loop_video_selection = data.get("loop_video_selection")
        intro_video_selection = data.get("intro_video_selection")
        return cls(
            base_dir=str(data["base_dir"]),
            config=dict(data["config"]),
            icon_path=str(data.get("icon_path", "")),
            loop_image_path=str(data.get("loop_image_path", "")),
            loop_video_selection=(
                VideoSelection.from_dict(loop_video_selection)
                if loop_video_selection
                else None
            ),
            intro_video_selection=(
                VideoSelection.from_dict(intro_video_selection)
                if intro_video_selection
                else None
            ),
        )


@dataclass
class MaterialExportRequest:
    """Serializable request payload for worker-driven export jobs."""

    base_dir: str
    output_dir: str
    config: dict[str, Any]
    icon_path: str = ""
    loop_image_path: str = ""
    loop_video_params: VideoExportParams | None = None
    intro_video_params: VideoExportParams | None = None

    def requires_ffmpeg(self) -> bool:
        intro_config = self.config.get("intro", {}) if isinstance(self.config, dict) else {}
        return bool(
            self.loop_image_path
            or self.loop_video_params is not None
            or self.intro_video_params is not None
            or bool(intro_config.get("enabled") and intro_config.get("file"))
        )

    def to_dict(self, *, ffmpeg_path: str = "") -> dict[str, Any]:
        return {
            "base_dir": self.base_dir,
            "output_dir": self.output_dir,
            "config": self.config,
            "icon_path": self.icon_path,
            "loop_image_path": self.loop_image_path,
            "loop_video_params": (
                self.loop_video_params.to_dict()
                if self.loop_video_params is not None
                else None
            ),
            "intro_video_params": (
                self.intro_video_params.to_dict()
                if self.intro_video_params is not None
                else None
            ),
            "ffmpeg_path": ffmpeg_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialExportRequest":
        loop_video_params = data.get("loop_video_params")
        intro_video_params = data.get("intro_video_params")
        return cls(
            base_dir=str(data["base_dir"]),
            output_dir=str(data["output_dir"]),
            config=dict(data["config"]),
            icon_path=str(data.get("icon_path", "")),
            loop_image_path=str(data.get("loop_image_path", "")),
            loop_video_params=(
                VideoExportParams.from_dict(loop_video_params)
                if loop_video_params
                else None
            ),
            intro_video_params=(
                VideoExportParams.from_dict(intro_video_params)
                if intro_video_params
                else None
            ),
        )
