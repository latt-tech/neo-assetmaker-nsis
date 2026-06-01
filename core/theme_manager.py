"""Theme manager for dark/light/system mode switching."""

from __future__ import annotations

import enum
from typing import Optional

from PyQt6.QtCore import QObject, QSettings, pyqtSignal


class ThemeMode(enum.Enum):
    """Application theme mode."""
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class ThemeManager(QObject):
    """Manages application theme with support for system-follow mode."""

    theme_changed = pyqtSignal(ThemeMode)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._settings = QSettings("ArknightsPassMaker", "ThemeSettings")
        self._current_mode = self._load_theme_mode()
        self._apply_theme(self._current_mode)

    @property
    def current_mode(self) -> ThemeMode:
        return self._current_mode

    def set_theme_mode(self, mode: ThemeMode) -> None:
        if mode == self._current_mode:
            return
        self._current_mode = mode
        self._save_theme_mode(mode)
        self._apply_theme(mode)
        self.theme_changed.emit(mode)

    def _load_theme_mode(self) -> ThemeMode:
        saved = self._settings.value("theme_mode", "system")
        try:
            return ThemeMode(saved)
        except ValueError:
            return ThemeMode.SYSTEM

    def _save_theme_mode(self, mode: ThemeMode) -> None:
        self._settings.setValue("theme_mode", mode.value)

    def _apply_theme(self, mode: ThemeMode) -> None:
        from qfluentwidgets import setTheme, Theme

        if mode == ThemeMode.DARK:
            setTheme(Theme.DARK)
        elif mode == ThemeMode.LIGHT:
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.AUTO)
