from pathlib import Path

from config.epconfig import (
    ArknightsOverlayOptions,
    EPConfig,
    ImageOverlayOptions,
    IntroConfig,
    LoopConfig,
    Overlay,
    OverlayType,
    ScreenType,
    Transition,
    TransitionOptions,
    TransitionType,
)
from core.validator import EPConfigValidator, ValidationLevel


def build_rich_config() -> EPConfig:
    return EPConfig(
        uuid="12345678-1234-1234-1234-1234567890ab",
        name="规则保护",
        description="round-trip",
        icon=r"C:\assets\icon-source.png",
        screen=ScreenType.S480x854,
        loop=LoopConfig(file=r"C:\assets\loop-source.mp4", is_image=True),
        intro=IntroConfig(enabled=True, file=r"C:\assets\intro-source.mp4"),
        transition_in=Transition(
            type=TransitionType.FADE,
            options=TransitionOptions(
                image=r"C:\assets\transition.png",
                background_color="#112233",
            ),
        ),
        transition_loop=Transition(type=TransitionType.MOVE),
        overlay=Overlay(
            type=OverlayType.ARKNIGHTS,
            arknights_options=ArknightsOverlayOptions(
                logo=r"C:\assets\logo.png",
                operator_class_icon=r"C:\assets\class.png",
            ),
        ),
    )


def test_epconfig_normalization_rules_are_preserved() -> None:
    normalized = build_rich_config().to_dict(normalize_paths=True)

    assert normalized["icon"] == "icon.png"
    assert normalized["loop"] == {"file": "loop.mp4", "is_image": True}
    assert normalized["intro"]["file"] == "intro.mp4"
    assert normalized["transition_in"]["options"]["image"] == "transition.png"
    assert normalized["overlay"]["options"]["logo"] == "ark_logo.png"
    assert normalized["overlay"]["options"]["operator_class_icon"] == "class_icon.png"


def test_epconfig_round_trip_keeps_public_behavior() -> None:
    original = build_rich_config()

    restored = EPConfig.from_dict(original.to_dict())

    assert restored.to_dict() == original.to_dict()
    assert '"name": "规则保护"' in original.to_json()


def test_epconfig_image_overlay_parsing_stays_compatible() -> None:
    restored = EPConfig.from_dict(
        {
            "uuid": "12345678-1234-1234-1234-1234567890ab",
            "screen": "360x640",
            "loop": {"file": "loop.mp4"},
            "overlay": {
                "type": "image",
                "options": {"appear_time": 1, "duration": 2, "image": "overlay.png"},
            },
        }
    )

    assert restored.overlay.type == OverlayType.IMAGE
    assert isinstance(restored.overlay.image_options, ImageOverlayOptions)
    assert restored.overlay.to_dict() == {
        "type": "image",
        "options": {"appear_time": 1, "duration": 2, "image": "overlay.png"},
    }


def test_validator_rules_stay_compatible() -> None:
    validator = EPConfigValidator()
    validator.validate(
        {
            "version": 2,
            "uuid": "not-a-uuid",
            "screen": "999x999",
            "loop": {"file": ""},
            "overlay": {
                "type": "image",
                "options": {"appear_time": 0, "duration": 0},
            },
        }
    )

    assert {result.field for result in validator.get_errors()} == {
        "version",
        "uuid",
        "screen",
        "loop.file",
    }
    assert {result.field for result in validator.get_warnings()} == {
        "overlay.options.appear_time",
        "overlay.options.duration",
    }
    assert validator.get_infos()[0].level == ValidationLevel.INFO
    assert validator.has_errors() is True
    assert validator.has_warnings() is True


def test_rule_facades_stay_thin() -> None:
    validator_source = Path("core/validator.py").read_text(encoding="utf-8")
    epconfig_source = Path("config/epconfig.py").read_text(encoding="utf-8")

    assert "_validate_" not in validator_source
    assert "loop.mp4" not in epconfig_source
    assert "ark_logo.png" not in epconfig_source
    assert "run_worker_validation" in validator_source
    assert "from core._protected.epconfig_core import" in epconfig_source
    assert EPConfigValidator.__module__ == "core.validator"
