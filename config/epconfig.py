"""Public EPConfig models backed by protected serialization rules."""

from __future__ import annotations

import json
import os
import uuid as uuid_lib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core._protected.epconfig_core import (
    arknights_overlay_options_from_dict,
    arknights_overlay_options_to_dict,
    epconfig_from_dict,
    epconfig_to_dict,
    epconfig_to_json,
    image_overlay_options_from_dict,
    image_overlay_options_to_dict,
    intro_from_dict,
    intro_to_dict,
    loop_from_dict,
    loop_to_dict,
    overlay_from_dict,
    overlay_to_dict,
    transition_from_dict,
    transition_options_from_dict,
    transition_options_to_dict,
    transition_to_dict,
)

CONFIG_FILENAME = "epconfig.json"


class ScreenType(Enum):
    S360x640 = "360x640"
    S480x854 = "480x854"
    S720x1080 = "720x1080"

    @classmethod
    def from_string(cls, value: str) -> "ScreenType":
        for member in cls:
            if member.value == value:
                return member
        return cls.S360x640


class TransitionType(Enum):
    NONE = "none"
    FADE = "fade"
    MOVE = "move"
    SWIPE = "swipe"

    @classmethod
    def from_string(cls, value: str) -> "TransitionType":
        for member in cls:
            if member.value == value:
                return member
        return cls.NONE


class OverlayType(Enum):
    NONE = "none"
    ARKNIGHTS = "arknights"
    IMAGE = "image"

    @classmethod
    def from_string(cls, value: str) -> "OverlayType":
        for member in cls:
            if member.value == value:
                return member
        return cls.NONE


@dataclass
class TransitionOptions:
    duration: int = 500000
    image: str = ""
    background_color: str = "#000000"

    def to_dict(self, normalize_paths: bool = False) -> dict:
        return transition_options_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict) -> "TransitionOptions":
        return transition_options_from_dict(data, cls)


@dataclass
class Transition:
    type: TransitionType = TransitionType.NONE
    options: Optional[TransitionOptions] = None

    def to_dict(self, normalize_paths: bool = False) -> dict | None:
        return transition_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Transition":
        return transition_from_dict(data, cls, TransitionType, TransitionOptions)


@dataclass
class LoopConfig:
    file: str = ""
    is_image: bool = False

    def to_dict(self, normalize_paths: bool = False) -> dict:
        return loop_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict) -> "LoopConfig":
        return loop_from_dict(data, cls)


@dataclass
class IntroConfig:
    enabled: bool = False
    file: str = ""
    duration: int = 5000000

    def to_dict(self, normalize_paths: bool = False) -> dict | None:
        return intro_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict | None) -> "IntroConfig":
        return intro_from_dict(data, cls)


@dataclass
class ArknightsOverlayOptions:
    appear_time: int = 100000
    operator_name: str = "OPERATOR"
    top_left_rhodes: str = ""
    top_right_bar_text: str = ""
    operator_code: str = "ARKNIGHTS - UNK0"
    barcode_text: str = "OPERATOR - ARKNIGHTS"
    aux_text: str = "Operator of Rhodes Island\nUndefined/Rhodes Island\n Hypergryph"
    staff_text: str = "STAFF"
    color: str = "#000000"
    logo: str = ""
    operator_class_icon: str = ""

    def to_dict(self, normalize_paths: bool = False) -> dict:
        return arknights_overlay_options_to_dict(
            self,
            normalize_paths=normalize_paths,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ArknightsOverlayOptions":
        return arknights_overlay_options_from_dict(data, cls)


@dataclass
class ImageOverlayOptions:
    appear_time: int = 100000
    duration: int = 0
    image: str = ""

    def to_dict(self, normalize_paths: bool = False) -> dict:
        return image_overlay_options_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict) -> "ImageOverlayOptions":
        return image_overlay_options_from_dict(data, cls)


@dataclass
class Overlay:
    type: OverlayType = OverlayType.NONE
    arknights_options: Optional[ArknightsOverlayOptions] = None
    image_options: Optional[ImageOverlayOptions] = None

    def to_dict(self, normalize_paths: bool = False) -> dict | None:
        return overlay_to_dict(self, normalize_paths=normalize_paths)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Overlay":
        return overlay_from_dict(
            data,
            cls,
            OverlayType,
            ArknightsOverlayOptions,
            ImageOverlayOptions,
        )


@dataclass
class EPConfig:
    version: int = 1
    uuid: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    name: str = ""
    description: str = ""
    icon: str = ""
    screen: ScreenType = ScreenType.S360x640
    loop: LoopConfig = field(default_factory=LoopConfig)
    intro: IntroConfig = field(default_factory=IntroConfig)
    transition_in: Transition = field(default_factory=Transition)
    transition_loop: Transition = field(default_factory=Transition)
    overlay: Overlay = field(default_factory=Overlay)

    def to_dict(self, normalize_paths: bool = False) -> dict:
        return epconfig_to_dict(self, normalize_paths=normalize_paths)

    def to_json(self, indent: int = 4, normalize_paths: bool = False) -> str:
        return epconfig_to_json(
            self,
            indent=indent,
            normalize_paths=normalize_paths,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EPConfig":
        return epconfig_from_dict(
            data,
            cls=cls,
            screen_type_cls=ScreenType,
            loop_cls=LoopConfig,
            intro_cls=IntroConfig,
            transition_cls=Transition,
            overlay_cls=Overlay,
            uuid_factory=lambda: str(uuid_lib.uuid4()),
        )

    @classmethod
    def load_from_file(cls, filepath: str) -> "EPConfig":
        with open(filepath, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return cls.from_dict(data)

    def save_to_file(self, filepath: str) -> None:
        try:
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            def _clean_surrogate_chars(obj: Any) -> Any:
                if isinstance(obj, str):
                    return "".join(c for c in obj if not (0xD800 <= ord(c) <= 0xDFFF))
                if isinstance(obj, dict):
                    return {k: _clean_surrogate_chars(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_clean_surrogate_chars(item) for item in obj]
                return obj

            cleaned_dict = _clean_surrogate_chars(self.to_dict())
            with open(filepath, "w", encoding="utf-8") as file_obj:
                json.dump(cleaned_dict, file_obj, ensure_ascii=False, indent=4)
        except PermissionError:
            raise RuntimeError(f"无法保存到 {filepath}，权限不足")

    def generate_new_uuid(self) -> None:
        self.uuid = str(uuid_lib.uuid4())

    def copy(self) -> "EPConfig":
        return EPConfig.from_dict(self.to_dict())
