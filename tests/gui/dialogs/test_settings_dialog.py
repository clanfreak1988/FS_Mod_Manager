"""Tests for SettingsDialog."""
import pytest

from fsmodmanager.core.model.settings import Settings
from fsmodmanager.gui.dialogs.settings_dialog import SettingsDialog


def _settings(**overrides) -> Settings:
    base = Settings(
        source_mod_folder="/mods",
        mod_collection_folder="/collection",
        savegame_path="/savegames",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class TestSettingsDialog:
    def test_fields_prepopulated(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert dialog._edit_source.text() == "/mods"
        assert dialog._edit_collection.text() == "/collection"
        assert dialog._edit_savegame.text() == "/savegames"

    def test_icon_column_checkbox_reflects_setting(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(visible_icon_column=False))
        qtbot.addWidget(dialog)
        assert not dialog._chk_icon_column.isChecked()

    def test_icon_column_checked_by_default(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(visible_icon_column=True))
        qtbot.addWidget(dialog)
        assert dialog._chk_icon_column.isChecked()

    def test_default_resolution_keeps_original_on_reject(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog.reject()
        # settings attribute should still be the copy of the original
        assert dialog.settings.source_mod_folder == "/mods"

    def test_accept_returns_modified_settings(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog._edit_source.setText("/new/mods")
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            dialog._on_accept()
        assert dialog.settings.source_mod_folder == "/new/mods"

    def test_accept_preserves_unchanged_fields(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog._edit_source.setText("/changed")
        dialog._on_accept()
        assert dialog.settings.mod_collection_folder == "/collection"
        assert dialog.settings.savegame_path == "/savegames"

    def test_checkbox_change_reflected_in_settings(self, qtbot) -> None:
        s = _settings(visible_icon_column=True)
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog._chk_icon_column.setChecked(False)
        dialog._on_accept()
        assert dialog.settings.visible_icon_column is False

    def test_original_not_mutated_on_accept(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog._edit_source.setText("/new")
        dialog._on_accept()
        # The original Settings object must be unchanged
        assert s.source_mod_folder == "/mods"

    def test_whitespace_stripped_from_paths(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        dialog._edit_source.setText("  /trimmed  ")
        dialog._on_accept()
        assert dialog.settings.source_mod_folder == "/trimmed"


class TestSettingsDialogTheme:
    def test_combo_defaults_to_system(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(theme="system"))
        qtbot.addWidget(dialog)
        assert dialog._combo_theme.currentText() == "System"

    def test_combo_prepopulated_dark(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(theme="dark"))
        qtbot.addWidget(dialog)
        assert dialog._combo_theme.currentText() == "Dunkel"

    def test_unknown_stored_theme_falls_back_to_system_item(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(theme="something-invalid"))
        qtbot.addWidget(dialog)
        assert dialog._combo_theme.currentText() == "System"

    def test_accept_returns_selected_theme(self, qtbot) -> None:
        dialog = SettingsDialog(_settings(theme="system"))
        qtbot.addWidget(dialog)
        dialog._combo_theme.setCurrentIndex(2)  # "Dunkel"
        dialog._on_accept()
        assert dialog.settings.theme == "dark"

    def test_selecting_theme_applies_it_live(self, qtbot, monkeypatch) -> None:
        applied = []
        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.settings_dialog.apply_theme",
            lambda theme: applied.append(theme),
        )
        dialog = SettingsDialog(_settings(theme="system"))
        qtbot.addWidget(dialog)
        applied.clear()  # ignore whatever _populate() triggered on construction
        dialog._combo_theme.setCurrentIndex(2)  # "Dunkel"
        assert applied == ["dark"]

    def test_reject_reverts_live_preview_to_original_theme(self, qtbot, monkeypatch) -> None:
        applied = []
        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.settings_dialog.apply_theme",
            lambda theme: applied.append(theme),
        )
        dialog = SettingsDialog(_settings(theme="light"))
        qtbot.addWidget(dialog)
        dialog._combo_theme.setCurrentIndex(2)  # preview "dark"
        dialog.reject()
        assert applied[-1] == "light"

    def test_closing_via_x_reverts_live_preview_like_cancel(self, qtbot, monkeypatch) -> None:
        """The window's close button (X) routes through Qt's default
        closeEvent straight into QDialog.reject() - bypassing the Cancel
        *button* entirely. Overriding reject() itself (rather than only
        reacting to the button box's rejected signal) is what makes this
        path get the same cleanup as clicking Cancel."""
        applied = []
        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.settings_dialog.apply_theme",
            lambda theme: applied.append(theme),
        )
        dialog = SettingsDialog(_settings(theme="light"))
        qtbot.addWidget(dialog)
        dialog.show()  # close() on a never-shown widget is a no-op in Qt
        dialog._combo_theme.setCurrentIndex(2)  # preview "dark"
        dialog.close()  # simulates clicking the window's X
        assert applied[-1] == "light"
        assert dialog.result() == dialog.DialogCode.Rejected


class TestSettingsDialogValidation:
    """OK button gating and label colouring based on path existence."""

    def test_ok_disabled_when_paths_missing(self, qtbot) -> None:
        """Paths that don't exist → OK button disabled."""
        s = _settings(
            source_mod_folder="/nonexistent_abc",
            mod_collection_folder="/nonexistent_def",
            savegame_path="/nonexistent_ghi",
        )
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert not dialog._ok_btn.isEnabled()

    def test_ok_enabled_when_all_paths_exist(self, qtbot, tmp_path) -> None:
        """All three paths exist → OK button enabled."""
        src = tmp_path / "src"; src.mkdir()
        col = tmp_path / "col"; col.mkdir()
        sav = tmp_path / "sav"; sav.mkdir()
        s = _settings(
            source_mod_folder=str(src),
            mod_collection_folder=str(col),
            savegame_path=str(sav),
        )
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert dialog._ok_btn.isEnabled()

    def test_ok_re_enabled_when_path_becomes_valid(self, qtbot, tmp_path) -> None:
        """Typing a valid path into a previously missing field re-enables OK."""
        src = tmp_path / "src"; src.mkdir()
        col = tmp_path / "col"; col.mkdir()
        sav = tmp_path / "sav"; sav.mkdir()
        s = _settings(
            source_mod_folder="/nonexistent",
            mod_collection_folder=str(col),
            savegame_path=str(sav),
        )
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert not dialog._ok_btn.isEnabled()
        dialog._edit_source.setText(str(src))
        assert dialog._ok_btn.isEnabled()

    def test_source_label_red_when_path_missing(self, qtbot) -> None:
        s = _settings(source_mod_folder="/nonexistent_xyz")
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert "red" in dialog._lbl_source.styleSheet()

    def test_source_label_green_when_path_exists(self, qtbot, tmp_path) -> None:
        src = tmp_path / "src"; src.mkdir()
        col = tmp_path / "col"; col.mkdir()
        sav = tmp_path / "sav"; sav.mkdir()
        s = _settings(
            source_mod_folder=str(src),
            mod_collection_folder=str(col),
            savegame_path=str(sav),
        )
        dialog = SettingsDialog(s)
        qtbot.addWidget(dialog)
        assert "green" in dialog._lbl_source.styleSheet()


class TestSettingsDialogFirstRun:
    """first_run=True specific behaviour."""

    def test_cancel_button_hidden_on_first_run(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s, first_run=True)
        qtbot.addWidget(dialog)
        # In first-run mode only one button (Weiter) is in the button box
        buttons = dialog._btn_box.buttons()
        assert len(buttons) == 1
        assert buttons[0].text() == "Weiter"

    def test_weiter_disabled_when_paths_missing(self, qtbot) -> None:
        s = _settings(source_mod_folder="/nonexistent_abc")
        dialog = SettingsDialog(s, first_run=True)
        qtbot.addWidget(dialog)
        assert not dialog._ok_btn.isEnabled()

    def test_weiter_enabled_when_all_paths_exist(self, qtbot, tmp_path) -> None:
        src = tmp_path / "src"; src.mkdir()
        col = tmp_path / "col"; col.mkdir()
        sav = tmp_path / "sav"; sav.mkdir()
        s = _settings(
            source_mod_folder=str(src),
            mod_collection_folder=str(col),
            savegame_path=str(sav),
        )
        dialog = SettingsDialog(s, first_run=True)
        qtbot.addWidget(dialog)
        assert dialog._ok_btn.isEnabled()

    def test_hint_label_shown_on_first_run(self, qtbot) -> None:
        from PySide6.QtWidgets import QLabel
        s = _settings()
        dialog = SettingsDialog(s, first_run=True)
        qtbot.addWidget(dialog)
        # The layout's first widget should be the hint QLabel
        root_layout = dialog.layout()
        hint_item = root_layout.itemAt(0).widget()
        assert isinstance(hint_item, QLabel)
        assert "Pfade" in hint_item.text()

    def test_window_title_set_to_erststart(self, qtbot) -> None:
        s = _settings()
        dialog = SettingsDialog(s, first_run=True)
        qtbot.addWidget(dialog)
        assert "Erststart" in dialog.windowTitle()
