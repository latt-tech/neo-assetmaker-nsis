"""Protected serialization and parsing rules for EPConfig models."""

from __future__ import annotations

import json
import os
from typing import Any, Callable


def transition_options_to_dict(options: Any, normalize_paths: bool = False) -> dict:
    result = {
        "duration": options.duration,
        "background_color": options.background_color,
    }
    if options.image:
        result["image"] = (
            os.path.basename(options.image) if normalize_paths else options.image
        )
    return result


def transition_options_from_dict(data: dict, cls: type[Any]) -> Any:
    return cls(
        duration=data.get("duration", 500000),
        image=data.get("image", ""),
        background_color=data.get("background_color", "#000000"),
    )


def transition_to_dict(transition: Any, normalize_paths: bool = False) -> dict | None:
    if transition.type.value == "none":
        return None
    result = {"type": transition.type.value}
    if transition.options:
        result["options"] = transition.options.to_dict(normalize_paths=normalize_paths)
    return result


def transition_from_dict(
    data: dict | None,
    cls: type[Any],
    transition_type_cls: type[Any],
    transition_options_cls: type[Any],
) -> Any:
    if not data:
        return cls()
    transition_type = transition_type_cls.from_string(data.get("type", "none"))
    options = None
    if "options" in data:
        options = transition_options_cls.from_dict(data["options"])
    return cls(type=transition_type, options=options)


def loop_to_dict(loop: Any, normalize_paths: bool = False) -> dict:
    result = {
        "file": "loop.mp4" if normalize_paths and loop.file else loop.file,
    }
    if loop.is_image:
        result["is_image"] = True
    return result


def loop_from_dict(data: dict, cls: type[Any]) -> Any:
    return cls(
        file=data.get("file", ""),
        is_image=data.get("is_image", False),
    )


def intro_to_dict(intro: Any, normalize_paths: bool = False) -> dict | None:
    if not intro.enabled:
        return None
    return {
        "enabled": True,
        "file": "intro.mp4" if normalize_paths and intro.file else intro.file,
        "duration": intro.duration,
    }


def intro_from_dict(data: dict | None, cls: type[Any]) -> Any:
    if not data:
        return cls()
    return cls(
        enabled=data.get("enabled", False),
        file=data.get("file", ""),
        duration=data.get("duration", 5000000),
    )


def arknights_overlay_options_to_dict(
    options: Any,
    normalize_paths: bool = False,
) -> dict:
    result = {
        "appear_time": options.appear_time,
        "operator_name": options.operator_name,
        "operator_code": options.operator_code,
        "barcode_text": options.barcode_text,
        "aux_text": options.aux_text,
        "staff_text": options.staff_text,
        "color": options.color,
    }
    if options.top_left_rhodes:
        result["top_left_rhodes"] = options.top_left_rhodes
    if options.top_right_bar_text:
        result["top_right_bar_text"] = options.top_right_bar_text
    if options.logo:
        result["logo"] = "ark_logo.png" if normalize_paths else options.logo
    if options.operator_class_icon:
        if options.operator_class_icon.startswith("class_icons/"):
            result["operator_class_icon"] = options.operator_class_icon
        else:
            result["operator_class_icon"] = (
                "class_icon.png" if normalize_paths else options.operator_class_icon
            )
    return result


def arknights_overlay_options_from_dict(data: dict, cls: type[Any]) -> Any:
    return cls(
        appear_time=data.get("appear_time", 100000),
        operator_name=data.get("operator_name", "OPERATOR"),
        top_left_rhodes=data.get("top_left_rhodes", ""),
        top_right_bar_text=data.get("top_right_bar_text", ""),
        operator_code=data.get("operator_code", "ARKNIGHTS - UNK0"),
        barcode_text=data.get("barcode_text", "OPERATOR - ARKNIGHTS"),
        aux_text=data.get(
            "aux_text",
            "Operator of Rhodes Island\nUndefined/Rhodes Island\n Hypergryph",
        ),
        staff_text=data.get("staff_text", "STAFF"),
        color=data.get("color", "#000000"),
        logo=data.get("logo", ""),
        operator_class_icon=data.get("operator_class_icon", ""),
    )


def image_overlay_options_to_dict(options: Any, normalize_paths: bool = False) -> dict:
    result = {
        "appear_time": options.appear_time,
        "duration": options.duration,
    }
    if options.image:
        result["image"] = "overlay.png" if normalize_paths else options.image
    return result


def image_overlay_options_from_dict(data: dict, cls: type[Any]) -> Any:
    return cls(
        appear_time=data.get("appear_time", 100000),
        duration=data.get("duration", 0),
        image=data.get("image", ""),
    )


def overlay_to_dict(overlay: Any, normalize_paths: bool = False) -> dict | None:
    if overlay.type.value == "none":
        return None
    result = {"type": overlay.type.value}
    if overlay.type.value == "arknights" and overlay.arknights_options:
        result["options"] = overlay.arknights_options.to_dict(
            normalize_paths=normalize_paths
        )
    elif overlay.type.value == "image" and overlay.image_options:
        result["options"] = overlay.image_options.to_dict(
            normalize_paths=normalize_paths
        )
    return result


def overlay_from_dict(
    data: dict | None,
    cls: type[Any],
    overlay_type_cls: type[Any],
    arknights_options_cls: type[Any],
    image_options_cls: type[Any],
) -> Any:
    if not data:
        return cls()
    overlay_type = overlay_type_cls.from_string(data.get("type", "none"))
    arknights_options = None
    image_options = None
    if overlay_type.value == "arknights" and "options" in data:
        arknights_options = arknights_options_cls.from_dict(data["options"])
    elif overlay_type.value == "image" and "options" in data:
        image_options = image_options_cls.from_dict(data["options"])
    return cls(
        type=overlay_type,
        arknights_options=arknights_options,
        image_options=image_options,
    )


def epconfig_to_dict(config: Any, normalize_paths: bool = False) -> dict:
    result = {
        "version": config.version,
        "uuid": config.uuid,
        "screen": config.screen.value,
        "loop": config.loop.to_dict(normalize_paths=normalize_paths),
    }
    if config.name:
        result["name"] = config.name
    if config.description:
        result["description"] = config.description
    if config.icon:
        result["icon"] = "icon.png" if normalize_paths else config.icon

    intro_dict = config.intro.to_dict(normalize_paths=normalize_paths)
    if intro_dict:
        result["intro"] = intro_dict

    transition_in_dict = config.transition_in.to_dict(
        normalize_paths=normalize_paths
    )
    if transition_in_dict:
        result["transition_in"] = transition_in_dict

    transition_loop_dict = config.transition_loop.to_dict(
        normalize_paths=normalize_paths
    )
    if transition_loop_dict:
        result["transition_loop"] = transition_loop_dict

    overlay_dict = config.overlay.to_dict(normalize_paths=normalize_paths)
    if overlay_dict:
        result["overlay"] = overlay_dict

    return result


def epconfig_to_json(
    config: Any,
    indent: int = 4,
    normalize_paths: bool = False,
) -> str:
    return json.dumps(
        epconfig_to_dict(config, normalize_paths=normalize_paths),
        ensure_ascii=False,
        indent=indent,
    )


def epconfig_from_dict(
    data: dict,
    *,
    cls: type[Any],
    screen_type_cls: type[Any],
    loop_cls: type[Any],
    intro_cls: type[Any],
    transition_cls: type[Any],
    overlay_cls: type[Any],
    uuid_factory: Callable[[], str],
) -> Any:
    return cls(
        version=data.get("version", 1),
        uuid=data.get("uuid", uuid_factory()),
        name=data.get("name", ""),
        description=data.get("description", ""),
        icon=data.get("icon", ""),
        screen=screen_type_cls.from_string(data.get("screen", "360x640")),
        loop=loop_cls.from_dict(data.get("loop", {})),
        intro=intro_cls.from_dict(data.get("intro")),
        transition_in=transition_cls.from_dict(data.get("transition_in")),
        transition_loop=transition_cls.from_dict(data.get("transition_loop")),
        overlay=overlay_cls.from_dict(data.get("overlay")),
    )
