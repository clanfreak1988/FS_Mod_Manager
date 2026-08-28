"""Tests for gui/theme.py.

Note on approach: the whole test suite runs under QT_QPA_PLATFORM=offscreen
(see tests/conftest.py), and that platform plugin doesn't actually implement
color-scheme propagation - QStyleHints.setColorScheme() silently has no
observable effect on styleHints().colorScheme() there, even though it does
change QGuiApplication.palette() live on a real platform (verified manually
against the default "xcb" platform during development). So these tests
mock QGuiApplication.styleHints() and assert the *calls* our code makes
(setColorScheme(Light/Dark) vs. unsetColorScheme()) rather than depending on
the offscreen plugin to report the resulting state back.
"""
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from fsmodmanager.gui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    apply_theme,
    detected_system_theme,
)


def _mock_style_hints() -> MagicMock:
    hints = MagicMock()
    # Explicitly present so the hasattr() feature-detection in apply_theme()
    # sees a Qt 6.8+-shaped styleHints object.
    hints.setColorScheme = MagicMock()
    hints.unsetColorScheme = MagicMock()
    hints.colorScheme = MagicMock(return_value=Qt.ColorScheme.Unknown)
    return hints


class TestApplyTheme:
    def test_light_calls_set_color_scheme_light(self) -> None:
        hints = _mock_style_hints()
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            apply_theme(THEME_LIGHT)
        hints.setColorScheme.assert_called_once_with(Qt.ColorScheme.Light)
        hints.unsetColorScheme.assert_not_called()

    def test_dark_calls_set_color_scheme_dark(self) -> None:
        hints = _mock_style_hints()
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            apply_theme(THEME_DARK)
        hints.setColorScheme.assert_called_once_with(Qt.ColorScheme.Dark)
        hints.unsetColorScheme.assert_not_called()

    def test_system_calls_unset_color_scheme(self) -> None:
        hints = _mock_style_hints()
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            apply_theme(THEME_SYSTEM)
        hints.unsetColorScheme.assert_called_once()
        hints.setColorScheme.assert_not_called()

    def test_unknown_value_falls_back_to_unset(self) -> None:
        hints = _mock_style_hints()
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            apply_theme("does-not-exist")
        hints.unsetColorScheme.assert_called_once()
        hints.setColorScheme.assert_not_called()

    def test_noop_when_style_hints_lacks_set_color_scheme(self) -> None:
        """Graceful degradation on Qt < 6.8, which has no
        setColorScheme()/unsetColorScheme() at all."""
        hints = MagicMock(spec=["colorScheme"])  # no set/unsetColorScheme
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            apply_theme(THEME_DARK)  # must not raise

    def test_real_qapplication_smoke(self, qtbot) -> None:
        """Not mocked: just verifies the real call sequence doesn't raise
        against an actual QGuiApplication/QStyleHints instance."""
        apply_theme(THEME_DARK)
        apply_theme(THEME_LIGHT)
        apply_theme(THEME_SYSTEM)


class TestDetectedSystemTheme:
    def test_maps_dark_scheme(self) -> None:
        hints = _mock_style_hints()
        hints.colorScheme.return_value = Qt.ColorScheme.Dark
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            assert detected_system_theme() == THEME_DARK

    def test_maps_light_scheme(self) -> None:
        hints = _mock_style_hints()
        hints.colorScheme.return_value = Qt.ColorScheme.Light
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            assert detected_system_theme() == THEME_LIGHT

    def test_unknown_scheme_defaults_to_light(self) -> None:
        hints = _mock_style_hints()
        hints.colorScheme.return_value = Qt.ColorScheme.Unknown
        with patch("fsmodmanager.gui.theme.QGuiApplication.styleHints", return_value=hints):
            assert detected_system_theme() == THEME_LIGHT

    def test_real_qapplication_smoke(self, qtbot) -> None:
        assert detected_system_theme() in (THEME_LIGHT, THEME_DARK)
