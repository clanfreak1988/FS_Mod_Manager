"""Tests for NewModsAssignDialog (mod → config assignment matrix)."""
from PySide6.QtCore import Qt

from fsmodmanager.core.model.mod import Mod
from fsmodmanager.gui.dialogs.new_mods_dialog import NewModsAssignDialog


def _mod(filename: str, title: str = "") -> Mod:
    return Mod(
        filename=filename,
        title=title,
        author="Autor",
        version="1.0.0.0",
        icon_filename="icon.png",
    )


def _dialog(qtbot, mods=None, configs=None) -> NewModsAssignDialog:
    mods = mods or [_mod("FS25_A.zip", "Mod A"), _mod("FS25_B.zip", "Mod B")]
    configs = configs or ["Alpha", "Beta", "Gamma"]
    dialog = NewModsAssignDialog(mods, configs)
    qtbot.addWidget(dialog)
    return dialog


class TestNewModsAssignDialog:
    def test_matrix_has_one_row_per_mod_and_one_column_per_config(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        assert dialog._table.rowCount() == 2
        assert dialog._table.columnCount() == 3

    def test_row_headers_show_title_and_tooltip_shows_filename(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        header = dialog._table.verticalHeaderItem(0)
        assert header.text() == "Mod A"
        assert header.toolTip() == "FS25_A.zip"

    def test_row_header_falls_back_to_filename_without_title(self, qtbot) -> None:
        dialog = _dialog(qtbot, mods=[_mod("FS25_NoTitle.zip")])
        assert dialog._table.verticalHeaderItem(0).text() == "FS25_NoTitle.zip"

    def test_nothing_checked_yields_empty_assignments(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        assert dialog.assignments == {}

    def test_single_checkbox_yields_one_assignment(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._table.item(0, 1).setCheckState(Qt.CheckState.Checked)
        assert dialog.assignments == {"Beta": ["FS25_A.zip"]}

    def test_one_mod_can_go_to_several_configs(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog._table.item(0, 2).setCheckState(Qt.CheckState.Checked)
        assert dialog.assignments == {
            "Alpha": ["FS25_A.zip"],
            "Gamma": ["FS25_A.zip"],
        }

    def test_several_mods_can_go_to_one_config(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog._table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        assert dialog.assignments == {"Alpha": ["FS25_A.zip", "FS25_B.zip"]}

    def test_all_button_assigns_every_mod_to_every_config(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._btn_all.click()
        assert dialog.assignments == {
            "Alpha": ["FS25_A.zip", "FS25_B.zip"],
            "Beta": ["FS25_A.zip", "FS25_B.zip"],
            "Gamma": ["FS25_A.zip", "FS25_B.zip"],
        }

    def test_none_button_clears_the_matrix(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._btn_all.click()
        dialog._btn_none.click()
        assert dialog.assignments == {}

    def test_column_header_click_checks_whole_config_column(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._on_column_header_clicked(1)
        assert dialog.assignments == {"Beta": ["FS25_A.zip", "FS25_B.zip"]}

    def test_column_header_click_again_unchecks_it(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._on_column_header_clicked(1)
        dialog._on_column_header_clicked(1)
        assert dialog.assignments == {}

    def test_row_header_click_checks_mod_in_every_config(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._on_row_header_clicked(1)
        assert dialog.assignments == {
            "Alpha": ["FS25_B.zip"],
            "Beta": ["FS25_B.zip"],
            "Gamma": ["FS25_B.zip"],
        }

    def test_partially_checked_column_is_filled_not_cleared(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        dialog._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog._on_column_header_clicked(0)
        assert dialog.assignments == {"Alpha": ["FS25_A.zip", "FS25_B.zip"]}

    def test_apply_accepts_and_skip_rejects(self, qtbot) -> None:
        dialog = _dialog(qtbot)
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            dialog._btn_apply.click()

        other = _dialog(qtbot)
        with qtbot.waitSignal(other.rejected, timeout=1000):
            other._btn_skip.click()


class TestMapMarker:
    def test_map_mods_are_marked_in_the_row_header(self, qtbot) -> None:
        """A config can only hold one map, so the user needs to see which of
        the new mods is one before ticking it everywhere."""
        map_mod = _mod("FS25_Map.zip", "Große Karte")
        map_mod.is_map = True
        dialog = _dialog(qtbot, mods=[map_mod, _mod("FS25_A.zip", "Mod A")])

        assert dialog._table.verticalHeaderItem(0).text() == "Große Karte (Karte)"
        assert dialog._table.verticalHeaderItem(1).text() == "Mod A"
