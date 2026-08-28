"""Shared application icon.

Mirrors Java Main.java, which loads `/icon.png` from the classpath resources
and adds it to the primary Stage (and every Alert/Dialog Stage) so it shows
up in the taskbar/window decoration. Here it's set once on QApplication
(main.py) and again explicitly on MainWindow, which together cover the
taskbar icon on Linux/Windows/macOS.
"""
from __future__ import annotations

from importlib.resources import files

from PySide6.QtGui import QIcon

_ICON_PACKAGE = "fsmodmanager.resources"
_ICON_FILENAME = "icon.png"


def app_icon() -> QIcon:
    """Return the application icon (512x512 PNG, same artwork as the Java version)."""
    icon_path = files(_ICON_PACKAGE) / _ICON_FILENAME
    return QIcon(str(icon_path))
