"""Public facade for protected video-processing behavior."""

from core._protected.video_core import X264_PARAMS, VideoInfo, VideoProcessor, find_ffmpeg

__all__ = ["X264_PARAMS", "VideoInfo", "VideoProcessor", "find_ffmpeg"]

