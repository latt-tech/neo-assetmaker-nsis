"""Public facade for protected image-processing behavior."""

from core._protected.image_core import ImageProcessor

ImageProcessor.__module__ = __name__

__all__ = ["ImageProcessor"]
