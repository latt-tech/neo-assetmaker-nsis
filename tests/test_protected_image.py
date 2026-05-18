from pathlib import Path

import numpy as np

from core.image_processor import ImageProcessor


def test_image_processor_round_trip_png(tmp_path: Path) -> None:
    image = np.array(
        [
            [[10, 20, 30], [40, 50, 60]],
            [[70, 80, 90], [100, 110, 120]],
        ],
        dtype=np.uint8,
    )
    output = tmp_path / "sample.png"

    assert ImageProcessor.save_image(image, str(output)) is True

    loaded = ImageProcessor.load_image(str(output))

    assert loaded is not None
    assert loaded.shape == image.shape
    assert np.array_equal(loaded, image)


def test_image_processor_resizes_and_preserves_expected_shapes() -> None:
    image = np.zeros((20, 40, 3), dtype=np.uint8)

    logo = ImageProcessor.process_for_logo(image)
    overlay = ImageProcessor.process_for_overlay(image, "360x640")

    assert logo.shape == (256, 256, 4)
    assert overlay.shape == (640, 360, 4)


def test_image_processor_converts_gray_to_bgra_and_rotates() -> None:
    image = np.array([[1, 2], [3, 4]], dtype=np.uint8)

    bgra = ImageProcessor.ensure_bgra(image)
    rotated = ImageProcessor.rotate_180(bgra)

    assert bgra.shape == (2, 2, 4)
    assert np.array_equal(bgra[..., 3], np.full((2, 2), 255, dtype=np.uint8))
    assert rotated[0, 0, 0] == bgra[1, 1, 0]


def test_image_processor_info_and_public_facade(tmp_path: Path) -> None:
    image = np.zeros((3, 5, 4), dtype=np.uint8)
    output = tmp_path / "info.png"
    ImageProcessor.save_image(image, str(output))

    info = ImageProcessor.get_image_info(str(output))
    facade_source = Path("core/image_processor.py").read_text(encoding="utf-8")

    assert info == {
        "width": 5,
        "height": 3,
        "channels": 4,
        "has_alpha": True,
        "size_str": "5x3",
    }
    assert "class ImageProcessor" not in facade_source
    assert "from core._protected.image_core import ImageProcessor" in facade_source
    assert ImageProcessor.__module__ == "core.image_processor"
