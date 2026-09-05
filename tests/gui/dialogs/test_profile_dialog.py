"""Tests for ProfileEditDialog (create/edit one FS installation)."""
from pathlib import Path

import pytest

from fsmodmanager.core.model.game_profile import GameProfile
from fsmodmanager.gui.dialogs.profile_dialog import ProfileEditDialog


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A game home whose three folders all exist."""
    (tmp_path / "mods").mkdir()
    (tmp_path / "LS_mods").mkdir()
    return tmp_path


def _profile(home: Path, name: str = "FS25") -> GameProfile:
    return GameProfile(
        name=name,
        source_mod_folder=str(home / "mods"),
        mod_collection_folder=str(home / "LS_mods"),
        savegame_path=str(home),
    )


class TestEditExisting:
    def test_form_is_prefilled(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        assert dialog._edit_name.text() == "FS25"
        assert dialog._edit_source.text() == str(home / "mods")
        assert dialog._edit_collection.text() == str(home / "LS_mods")

    def test_no_template_row_when_editing(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        assert not hasattr(dialog, "_combo_template")

    def test_accept_returns_the_edited_profile(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        dialog._edit_name.setText("FS25 (Haupt)")
        dialog._on_accept()
        assert dialog.profile.name == "FS25 (Haupt)"
        assert dialog.profile.mod_collection_folder == str(home / "LS_mods")

    def test_whitespace_is_stripped(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        dialog._edit_name.setText("  FS22  ")
        dialog._on_accept()
        assert dialog.profile.name == "FS22"


class TestValidation:
    def test_ok_enabled_when_everything_exists(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        assert dialog._ok_btn.isEnabled()

    def test_ok_disabled_without_a_name(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        dialog._edit_name.setText("")
        assert not dialog._ok_btn.isEnabled()

    def test_ok_disabled_for_a_name_already_taken(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home), existing_names=["FS22"])
        qtbot.addWidget(dialog)
        dialog._edit_name.setText("fs22")
        assert not dialog._ok_btn.isEnabled()

    def test_ok_disabled_for_a_missing_folder(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        dialog._edit_source.setText(str(home / "gibtsnicht"))
        assert not dialog._ok_btn.isEnabled()


class TestCollectionFolderCreation:
    def test_create_button_offered_only_when_missing(self, qtbot, home: Path) -> None:
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        assert not dialog._btn_mkdir.isEnabled()

        dialog._edit_collection.setText(str(home / "neu"))
        assert dialog._btn_mkdir.isEnabled()

    def test_create_button_makes_the_folder_and_unblocks_ok(self, qtbot, home: Path) -> None:
        """A freshly installed second FS version has no collection folder
        yet - without this the user could not finish the dialog at all."""
        dialog = ProfileEditDialog(_profile(home))
        qtbot.addWidget(dialog)
        dialog._edit_collection.setText(str(home / "neu"))
        assert not dialog._ok_btn.isEnabled()

        dialog._btn_mkdir.click()

        assert (home / "neu").is_dir()
        assert dialog._ok_btn.isEnabled()


class TestNewProfileTemplate:
    def test_template_prefills_name_and_paths(self, qtbot) -> None:
        from fsmodmanager.core.service.settings_service import FS_VERSIONS

        dialog = ProfileEditDialog()
        qtbot.addWidget(dialog)
        # First template is the newest release.
        _label, year = FS_VERSIONS[0]
        assert dialog._edit_name.text() == f"FS{year[-2:]}"
        assert dialog._edit_source.text().endswith("mods")
        assert f"FarmingSimulator{year}" in dialog._edit_collection.text()

    def test_switching_the_template_refills_the_form(self, qtbot) -> None:
        dialog = ProfileEditDialog()
        qtbot.addWidget(dialog)
        dialog._combo_template.setCurrentIndex(1)
        dialog._apply_template()
        assert dialog._edit_name.text() == "FS22"
        assert "FarmingSimulator2022" in dialog._edit_savegame.text()
