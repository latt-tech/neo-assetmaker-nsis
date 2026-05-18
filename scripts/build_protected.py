"""Build the material-making protected core modules with Cython."""

from __future__ import annotations

from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "protected_src" / "material_core"
PROTECTED_MODULES = [
    "core._protected.export_core",
    "core._protected.video_core",
    "core._protected.overlay_core",
    "core._protected.epconfig_core",
    "core._protected.validator_core",
    "core._protected.image_core",
]


def build_extensions() -> None:
    extensions = [
        Extension(
            module_name,
            [str(SOURCE_ROOT / f"{module_name.rsplit('.', 1)[-1]}.py")],
        )
        for module_name in PROTECTED_MODULES
    ]
    setup(
        name="neo-assetmaker-protected-core",
        packages=[],
        ext_modules=cythonize(
            extensions,
            compiler_directives={"language_level": "3"},
        ),
        script_args=["build_ext", "--inplace"],
    )


if __name__ == "__main__":
    build_extensions()
