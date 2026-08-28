"""Dark/Light theme switching.

New feature, no Java equivalent. Uses Qt's native color-scheme hint
(QStyleHints.setColorScheme(), added in Qt 6.8) rather than hand-rolled
QPalette colors: it re-styles the whole application live, follows the same
mechanism the OS itself uses to tell apps "the user switched to dark mode",
and needs no palette/stylesheet maintenance on our side.

Settings.theme holds one of "system" | "light" | "dark":
  "system" (default) – follow the OS setting; also what unsetColorScheme()
                        reverts to, so this is always a safe fallback.
  "light" / "dark"    – force that scheme regardless of the OS setting.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

log = logging.getLogger(__name__)

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
VALID_THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

_SCHEME_BY_THEME = {
    THEME_LIGHT: Qt.ColorScheme.Light,
    THEME_DARK: Qt.ColorScheme.Dark,
}


def apply_theme(theme: str) -> None:
    """Apply the given theme ("system" | "light" | "dark") app-wide.

    Unknown values fall back to "system", same as a fresh Settings.theme
    default. Safe to call repeatedly (e.g. right after the user changes it
    in the Settings dialog) - takes effect immediately, no restart needed.

    No-ops (with a debug log) on a Qt version older than 6.8, where
    QStyleHints.setColorScheme()/unsetColorScheme() don't exist yet - the
    app just keeps using whatever the OS/style already provides.
    """
    style_hints = QGuiApplication.styleHints()
    if not (
        hasattr(style_hints, "setColorScheme")
        and hasattr(style_hints, "unsetColorScheme")
    ):
        log.debug(
            "Qt style hints has no setColorScheme() (needs Qt 6.8+) - "
            "theme setting '%s' ignored, OS/style default is used.", theme
        )
        return

    scheme = _SCHEME_BY_THEME.get(theme)
    if scheme is None:
        style_hints.unsetColorScheme()
    else:
        style_hints.setColorScheme(scheme)


def detected_system_theme() -> str:
    """Best-effort readout of the OS's current color scheme, for display
    purposes only (e.g. an "System (aktuell: Dunkel)" label). Returns
    "light" or "dark"; defaults to "light" if Qt can't tell (Unknown, or
    Qt < 6.8 without the colorScheme() readout)."""
    style_hints = QGuiApplication.styleHints()
    scheme = getattr(style_hints, "colorScheme", lambda: Qt.ColorScheme.Unknown)()
    if scheme == Qt.ColorScheme.Dark:
        return THEME_DARK
    return THEME_LIGHT
