"""End-to-End integration tests – Linux, simulated FS structure.

These tests exercise the complete workflow from startup to activation using
a realistic but synthetic directory structure.  No real FS installation or
Windows is required.

Directory layout created per test:
  tmp/
    mods/          ← source_mod_folder  (symlinks land here after activate)
    collection/    ← mod_collection_folder (real ZIPs live here)
    savegames/
      savegame1/careerSavegame.xml
    data/          ← settings persistence
    configs/       ← configuration JSON files

Workflow covered:
  1. initialize() → collect mods from mods/ into collection/
  2. available_mods populated from collection/
  3. create_config / select_config / move_all / save_config
  4. activate_config → symlinks in mods/
  5. deactivate path (new activate with different set)
  6. import_savegame → config from XML, mods selected
  7. Settings round-trip (change paths, reload)
  8. Full GUI window starts, shows mods, responds to button clicks
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from fsmodmanager.core.model.settings import Settings
from fsmodmanager.core.service.collection_service import CollectionService, ConflictResolution
from fsmodmanager.core.service.config_service import ConfigService
from fsmodmanager.core.service.link_service import LinkService
from fsmodmanager.core.service.settings_service import SettingsService
from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel

# ── helpers ───────────────────────────────────────────────────────────────────

_MOD_DESC = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<modDesc descVersion="72">
    <author>{author}</author>
    <version>{version}</version>
    <title><en>{title}</en></title>
    <iconFilename>icon.png</iconFilename>
</modDesc>"""

_SAVEGAME_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<careerSavegame>
  <mod modName="FS25_ModA" title="Mod A" version="1.0.0.0" required="false" fileHash="abc"/>
  <mod modName="FS25_ModB" title="Mod B" version="1.0.0.0" required="false" fileHash="def"/>
  <mod modName="pdlc_SomeContent" title="PDLC" version="1.0" required="true" fileHash="xyz"/>
</careerSavegame>"""


def _make_mod_zip(directory: Path, name: str, title: str, author: str = "Tester", version: str = "1.0.0.0") -> Path:
    """Create a minimal but valid mod ZIP with a real PNG icon."""
    p = directory / name
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("modDesc.xml", _MOD_DESC.format(title=title, author=author, version=version))
        # 2×2 white PNG
        from PIL import Image
        img = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        zf.writestr("icon.png", buf.getvalue())
    return p


def _make_fs_structure(tmp: Path) -> tuple[Path, Path, Path, Path]:
    """Return (source, collection, savegames, configs) dirs, all created."""
    source = tmp / "mods"
    collection = tmp / "collection"
    savegames = tmp / "savegames"
    configs = tmp / "configs"
    for d in (source, collection, savegames, configs):
        d.mkdir()
    return source, collection, savegames, configs


def _make_vm(tmp: Path) -> MainViewModel:
    """Create a ViewModel wired to an already-initialised FS structure under tmp.

    If settings.json already exists (e.g. a previous VM in the same test already
    wrote it), those settings are kept so that persisted state (active_modpack etc.)
    survives across simulated restarts.
    """
    source = tmp / "mods"
    collection = tmp / "collection"
    savegames = tmp / "savegames"
    configs = tmp / "configs"
    # Ensure dirs exist (idempotent)
    for d in (source, collection, savegames, configs):
        d.mkdir(exist_ok=True)
    data_dir = tmp / "data"
    svc = SettingsService(data_dir=data_dir)
    # Only write initial settings when no file exists yet
    if not svc.exists():
        svc.save(Settings(
            source_mod_folder=str(source),
            mod_collection_folder=str(collection),
            savegame_path=str(savegames),
            # Avoids the blocking "Konfigurationen aus Savegames erstellen?"
            # QMessageBox that _do_initialize() would otherwise show – nothing
            # answers it in a headless test, so it would hang forever.
            savegames_read=True,
        ))
    return MainViewModel(
        settings_service=SettingsService(data_dir=data_dir),
        config_service=ConfigService(configs_dir=configs),
        link_service=LinkService(),
        collection_service=CollectionService(),
    )


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_two_game_vm(tmp: Path) -> MainViewModel:
    """Two separate FS installations under tmp, FS25 active.

    Mirrors main.py's wiring: the configuration directory is derived from
    each profile's collection folder, so switching profiles also switches
    which configurations exist.
    """
    from fsmodmanager.core.model.game_profile import GameProfile

    for sub in ("fs25/mods", "fs25/collection", "fs22/mods", "fs22/collection"):
        (tmp / sub).mkdir(parents=True)
    _make_mod_zip(tmp / "fs25/collection", "FS25_Only.zip", "Nur FS25")
    _make_mod_zip(tmp / "fs22/collection", "FS22_Only.zip", "Nur FS22")

    def _profile(name: str, home: str) -> GameProfile:
        return GameProfile(
            name=name,
            source_mod_folder=str(tmp / home / "mods"),
            mod_collection_folder=str(tmp / home / "collection"),
            savegame_path=str(tmp / home),
            savegames_read=True,
        )

    data_dir = tmp / "data"
    SettingsService(data_dir=data_dir).save(Settings(
        source_mod_folder=str(tmp / "fs25/mods"),
        mod_collection_folder=str(tmp / "fs25/collection"),
        savegame_path=str(tmp / "fs25"),
        savegames_read=True,
        profiles=[_profile("FS25", "fs25"), _profile("FS22", "fs22")],
        active_profile="FS25",
    ))
    return MainViewModel(
        settings_service=SettingsService(data_dir=data_dir),
        config_service=ConfigService(configs_dir=tmp / "placeholder"),
        link_service=LinkService(),
        collection_service=CollectionService(),
        configs_dir_factory=lambda s: Path(s.mod_collection_folder).parent / "configs",
    )


@pytest.fixture()
def two_games(tmp_path, qtbot):
    """A shown MainWindow wired to two FS installations."""
    from fsmodmanager.gui.main_window import MainWindow

    vm = _make_two_game_vm(tmp_path)
    window = MainWindow(view_model=vm)
    qtbot.addWidget(window)
    _show_and_init(window, vm, qtbot)
    return window, vm


@pytest.fixture()
def fs(tmp_path):
    """Simulated FS structure with three mod ZIPs in the source folder."""
    source, collection, savegames, configs = _make_fs_structure(tmp_path)
    _make_mod_zip(source, "FS25_ModA.zip", "Mod A")
    _make_mod_zip(source, "FS25_ModB.zip", "Mod B")
    _make_mod_zip(source, "FS25_ModC.zip", "Mod C")
    sg_dir = savegames / "savegame1"
    sg_dir.mkdir()
    (sg_dir / "careerSavegame.xml").write_text(_SAVEGAME_XML, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def vm(fs, qtbot) -> MainViewModel:
    return _make_vm(fs)


# ── 1. Collection ─────────────────────────────────────────────────────────────

class TestCollectOnInit:
    def test_real_zips_moved_to_collection(self, vm, fs) -> None:
        vm.initialize()
        col = fs / "collection"
        zips = list(col.glob("*.zip"))
        assert len(zips) == 3

    def test_symlinks_created_in_source(self, vm, fs) -> None:
        vm.initialize()
        src = fs / "mods"
        links = [p for p in src.iterdir() if p.is_symlink()]
        assert len(links) == 3

    def test_symlinks_point_to_collection(self, vm, fs) -> None:
        vm.initialize()
        src = fs / "mods"
        col = fs / "collection"
        for link in src.iterdir():
            assert link.is_symlink()
            assert link.resolve().parent == col.resolve()

    def test_available_mods_populated(self, vm) -> None:
        vm.initialize()
        assert len(vm.available_mods) == 3

    def test_available_mods_are_parsed(self, vm) -> None:
        vm.initialize()
        titles = {m.title for m in vm.available_mods}
        assert titles == {"Mod A", "Mod B", "Mod C"}

    def test_already_linked_mods_not_reported_as_new(self, fs, qtbot) -> None:
        """A symlink already sitting in source_mod_folder (e.g. left over
        from an activate_config() in an earlier session) must not be
        reported via new_mods_detected - only the real, non-symlink zips
        found there are genuinely new this run. Re-scanning source for *any*
        symlink after collect() (the previous implementation) would also
        catch already-active mods and wrongly highlight them as new.
        """
        import os
        source = fs / "mods"
        collection = fs / "collection"
        target = collection / "FS25_AlreadyActive.zip"
        _make_mod_zip(collection, "FS25_AlreadyActive.zip", "Already Active")
        os.symlink(target, source / "FS25_AlreadyActive.zip")

        vm = _make_vm(fs)
        detected = []
        vm.new_mods_detected.connect(lambda names: detected.append(names))
        vm.initialize()

        assert detected, "Expected the 3 fixture mods to be reported as new"
        reported = set(detected[0])
        assert "FS25_AlreadyActive.zip" not in reported
        assert reported == {"FS25_ModA.zip", "FS25_ModB.zip", "FS25_ModC.zip"}

    def test_invalid_filename_triggers_warning_on_collect(self, fs, qtbot) -> None:
        """A newly dropped mod whose filename FS itself would reject (e.g. a
        browser-appended "(1)" from a duplicate download) must surface a
        warning immediately, instead of only showing up later in FS's log."""
        source = fs / "mods"
        _make_mod_zip(source, "FS25_AdvancedDamageSystem (1).zip", "Broken Name")

        vm = _make_vm(fs)
        warnings = []
        vm.warning_occurred.connect(lambda msg: warnings.append(msg))
        vm.initialize()

        assert any("FS25_AdvancedDamageSystem (1).zip" in w for w in warnings)
        assert any("Invalid mod name" in w for w in warnings)


class TestRenameMod:
    """MainViewModel.rename_mod() and friends - fixing a Mod.has_invalid_name
    filename, including the overwrite/keep/skip conflict flow."""

    @staticmethod
    def _find(mods, filename):
        return next(m for m in mods if m.filename == filename)

    def test_suggest_valid_mod_name(self, vm) -> None:
        assert vm.suggest_valid_mod_name("Bad Name (1).zip") == "BadName.zip"

    def test_rename_without_conflict(self, fs, qtbot) -> None:
        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        vm.initialize()

        mod = self._find(vm.available_mods, "FS25_Broken (1).zip")
        new_name = vm.suggest_valid_mod_name(mod.filename)
        assert vm.check_rename_conflict(mod, new_name) is None

        vm.rename_mod(mod, new_name)

        assert mod.filename == new_name
        assert any(m.filename == new_name for m in vm.available_mods)
        assert not any(m.filename == "FS25_Broken (1).zip" for m in vm.available_mods)
        assert (fs / "collection" / new_name).exists()

    def test_rename_preserves_selection(self, fs, qtbot) -> None:
        """Renaming a mod that's currently in "Ausgewählt" must not silently
        bounce it back to "Verfügbar"."""
        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()

        mod = self._find(vm.selected_mods, "FS25_Broken (1).zip")
        vm.rename_mod(mod, "FS25_Broken.zip")

        assert any(m.filename == "FS25_Broken.zip" for m in vm.selected_mods)
        assert not any(m.filename == "FS25_Broken.zip" for m in vm.available_mods)

    def test_rename_with_conflict_overwrite(self, fs, qtbot) -> None:
        source = fs / "mods"
        collection = fs / "collection"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken", author="New")
        vm = _make_vm(fs)
        vm.initialize()
        _make_mod_zip(collection, "FS25_Broken.zip", "Old Copy", author="Old")
        vm._load_mods_from_collection()

        mod = self._find(vm.available_mods, "FS25_Broken (1).zip")
        assert vm.check_rename_conflict(mod, "FS25_Broken.zip") is not None

        vm.rename_mod(mod, "FS25_Broken.zip", resolution=ConflictResolution.OVERWRITE)

        renamed = self._find(vm.available_mods, "FS25_Broken.zip")
        assert renamed.author == "New"
        assert not any(m.filename == "FS25_Broken (1).zip" for m in vm.available_mods)

    def test_rename_with_conflict_keep_existing_discards_invalid(self, fs, qtbot) -> None:
        source = fs / "mods"
        collection = fs / "collection"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        vm.initialize()
        _make_mod_zip(collection, "FS25_Broken.zip", "Existing")
        vm._load_mods_from_collection()

        mod = self._find(vm.available_mods, "FS25_Broken (1).zip")
        vm.rename_mod(mod, "FS25_Broken.zip", resolution=ConflictResolution.KEEP_EXISTING)

        assert not any(m.filename == "FS25_Broken (1).zip" for m in vm.available_mods)
        remaining = self._find(vm.available_mods, "FS25_Broken.zip")
        assert remaining.title == "Existing"

    def test_rename_with_conflict_skip_leaves_untouched(self, fs, qtbot) -> None:
        source = fs / "mods"
        collection = fs / "collection"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        vm.initialize()
        _make_mod_zip(collection, "FS25_Broken.zip", "Existing")
        vm._load_mods_from_collection()

        mod = self._find(vm.available_mods, "FS25_Broken (1).zip")
        vm.rename_mod(mod, "FS25_Broken.zip", resolution=ConflictResolution.SKIP)

        assert any(m.filename == "FS25_Broken (1).zip" for m in vm.available_mods)

    def test_rename_updates_saved_config_reference(self, fs, qtbot) -> None:
        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()

        mod = self._find(vm.selected_mods, "FS25_Broken (1).zip")
        vm.rename_mod(mod, "FS25_Broken.zip")

        stored = vm._config_svc.load("Hof1")
        assert "FS25_Broken.zip" in stored.mod_filenames
        assert "FS25_Broken (1).zip" not in stored.mod_filenames


class TestDeleteMod:
    def test_removes_from_collection_and_lists(self, vm, fs) -> None:
        vm.initialize()
        mod = next(m for m in vm.available_mods if m.filename == "FS25_ModA.zip")

        vm.delete_mod(mod)

        assert not (fs / "collection" / "FS25_ModA.zip").exists()
        assert not any(m.filename == "FS25_ModA.zip" for m in vm.available_mods)

    def test_removes_active_symlink(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.activate_config()

        mod = next(m for m in vm.selected_mods if m.filename == "FS25_ModA.zip")
        vm.delete_mod(mod)

        assert not (fs / "mods" / "FS25_ModA.zip").exists()

    def test_removes_from_saved_config_reference(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()

        mod = next(m for m in vm.selected_mods if m.filename == "FS25_ModA.zip")
        vm.delete_mod(mod)

        stored = vm._config_svc.load("Hof1")
        assert "FS25_ModA.zip" not in stored.mod_filenames

    def test_leaves_other_mods_untouched(self, vm, fs) -> None:
        vm.initialize()
        mod = next(m for m in vm.available_mods if m.filename == "FS25_ModA.zip")

        vm.delete_mod(mod)

        assert any(m.filename == "FS25_ModB.zip" for m in vm.available_mods)
        assert (fs / "collection" / "FS25_ModB.zip").exists()


# ── 2. Config lifecycle ───────────────────────────────────────────────────────

class TestConfigLifecycle:
    def test_create_and_save_config(self, vm) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()
        config = vm._config_svc.load("Hof1")
        assert len(config.mod_filenames) == 3

    def test_reload_config_restores_selection(self, vm) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()

        # Deselect by selecting empty config
        vm.select_config("Hof1")
        assert len(vm.selected_mods) == 3
        assert len(vm.available_mods) == 0

    def test_copy_config(self, vm) -> None:
        vm.initialize()
        vm.create_config("Original")
        vm.select_config("Original")
        vm.move_all_to_selected()
        vm.save_config()
        vm.copy_config("Original", "Kopie")
        kopie = vm._config_svc.load("Kopie")
        assert len(kopie.mod_filenames) == 3

    def test_rename_config(self, vm) -> None:
        vm.initialize()
        vm.create_config("Alt")
        vm.rename_config("Alt", "Neu")
        assert vm._config_svc.exists("Neu")
        assert not vm._config_svc.exists("Alt")

    def test_delete_config(self, vm) -> None:
        vm.initialize()
        vm.create_config("Temp")
        vm.delete_config("Temp")
        assert not vm._config_svc.exists("Temp")

    def test_partial_selection(self, vm) -> None:
        vm.initialize()
        vm.create_config("Partial")
        vm.select_config("Partial")
        mods_a = [m for m in vm.available_mods if m.filename == "FS25_ModA.zip"]
        vm.move_to_selected(mods_a)
        vm.save_config()
        config = vm._config_svc.load("Partial")
        assert config.mod_filenames == ["FS25_ModA.zip"]


# ── 3. Activate (symlink management) ─────────────────────────────────────────

class TestActivate:
    def test_activate_creates_symlinks_for_selected(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        mods_a = [m for m in vm.available_mods if "ModA" in m.filename]
        vm.move_to_selected(mods_a)
        vm.activate_config()
        src = fs / "mods"
        links = {p.name for p in src.iterdir() if p.is_symlink()}
        assert "FS25_ModA.zip" in links

    def test_activate_removes_previous_links(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.activate_config()

        # Switch to only ModA
        vm.select_config("Hof1")
        vm.move_all_to_available()
        mods_a = [m for m in vm.available_mods if "ModA" in m.filename]
        vm.move_to_selected(mods_a)
        vm.activate_config()

        src = fs / "mods"
        links = {p.name for p in src.iterdir() if p.is_symlink()}
        assert links == {"FS25_ModA.zip"}

    def test_activate_stores_active_modpack_in_settings(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.activate_config()
        # Reload settings from disk
        saved = SettingsService(data_dir=fs / "data").load()
        assert saved.active_modpack == "Hof1"

    def test_activate_not_restored_on_next_init(self, vm, fs) -> None:
        """No config is auto-selected on startup, even if one was active before.

        A pre-filled config name with a full "selected" list right after
        startup would falsely suggest those mods are already active, even
        though activate_config() has not run this session. The symlinks from
        the previous activation still exist on disk — only the GUI's
        pre-selection is suppressed.
        """
        vm.initialize()
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()
        vm.activate_config()

        # Fresh ViewModel — simulates app restart
        vm2 = _make_vm(fs)
        vm2.initialize()
        assert vm2.active_config_name == ""
        assert len(vm2.selected_mods) == 0
        assert len(vm2.available_mods) == 3

        # The setting itself is still persisted for reference...
        saved = SettingsService(data_dir=fs / "data").load()
        assert saved.active_modpack == "Hof1"
        # ...and the symlinks from the earlier activate_config() are untouched.
        links = {p.name for p in (fs / "mods").iterdir() if p.is_symlink()}
        assert links == {"FS25_ModA.zip", "FS25_ModB.zip", "FS25_ModC.zip"}


# ── 4. Savegame import ────────────────────────────────────────────────────────

class TestSavegameImport:
    def test_import_creates_config(self, vm, fs) -> None:
        vm.initialize()
        xml = fs / "savegames" / "savegame1" / "careerSavegame.xml"
        vm.import_savegame(xml)
        assert vm._config_svc.exists("savegame1")

    def test_import_config_contains_non_pdlc_mods(self, vm, fs) -> None:
        vm.initialize()
        xml = fs / "savegames" / "savegame1" / "careerSavegame.xml"
        vm.import_savegame(xml)
        config = vm._config_svc.load("savegame1")
        filenames = set(config.mod_filenames)
        assert "FS25_ModA.zip" in filenames
        assert "FS25_ModB.zip" in filenames

    def test_import_pdlc_filtered_out(self, vm, fs) -> None:
        vm.initialize()
        xml = fs / "savegames" / "savegame1" / "careerSavegame.xml"
        vm.import_savegame(xml)
        config = vm._config_svc.load("savegame1")
        assert not any("pdlc_" in f for f in config.mod_filenames)

    def test_import_selects_matching_available_mods(self, vm, fs) -> None:
        vm.initialize()
        xml = fs / "savegames" / "savegame1" / "careerSavegame.xml"
        vm.import_savegame(xml)
        # ModA and ModB exist in collection → should be in selected_mods
        selected = {m.filename for m in vm.selected_mods}
        assert "FS25_ModA.zip" in selected
        assert "FS25_ModB.zip" in selected

    def test_import_unknown_mods_not_in_selected(self, vm, fs) -> None:
        """Mods referenced in savegame but absent from collection stay absent."""
        vm.initialize()
        xml = fs / "savegames" / "savegame1" / "careerSavegame.xml"
        vm.import_savegame(xml)
        selected = {m.filename for m in vm.selected_mods}
        # ModC is in the collection but NOT in the savegame XML
        assert "FS25_ModC.zip" not in selected


# ── 5. Settings persistence ───────────────────────────────────────────────────

class TestSettingsPersistence:
    def test_settings_saved_and_reloaded(self, vm, fs) -> None:
        vm.initialize()
        new_settings = Settings(
            source_mod_folder=str(fs / "mods"),
            mod_collection_folder=str(fs / "collection"),
            savegame_path=str(fs / "savegames"),
            visible_icon_column=False,
        )
        vm.save_settings(new_settings)
        reloaded = SettingsService(data_dir=fs / "data").load()
        assert reloaded.visible_icon_column is False

    def test_active_modpack_persists(self, vm, fs) -> None:
        vm.initialize()
        vm.create_config("Farm")
        vm.select_config("Farm")
        vm.move_all_to_selected()
        vm.activate_config()
        reloaded = SettingsService(data_dir=fs / "data").load()
        assert reloaded.active_modpack == "Farm"


# ── 6. GUI end-to-end ─────────────────────────────────────────────────────────

def _show_and_init(window, vm, qtbot, timeout: int = 2000) -> None:
    """Show the window and block until MainViewModel.initialize() completes.

    initialize() is triggered via QTimer.singleShot(0) in showEvent, so it
    fires on the first event-loop tick after the window becomes visible.
    We wait for available_mods_changed (always emitted by _load_mods_from_collection)
    as the reliable completion marker.
    """
    with qtbot.waitSignal(vm.available_mods_changed, timeout=timeout):
        window.show()
    qtbot.waitExposed(window)


def _patch_new_config_dialog(name: str):
    """Answer MainWindow._on_new_config()'s custom QDialog with *name*.

    _on_new_config() builds its own QDialog (not QInputDialog), so the
    prompt must be answered by patching QDialog.exec: fill the dialog's
    QLineEdit and accept, exactly like a user typing a name and clicking OK.
    """
    from unittest.mock import patch
    from PySide6.QtWidgets import QDialog, QLineEdit

    def fake_exec(self_dialog):
        edit = self_dialog.findChild(QLineEdit)
        if edit is not None:
            edit.setText(name)
        return QDialog.DialogCode.Accepted

    return patch("fsmodmanager.gui.main_window.QDialog.exec", fake_exec)


class TestGuiEndToEnd:
    def test_first_run_opens_settings_dialog(self, tmp_path, qtbot) -> None:
        """On first run (no settings.json) SettingsDialog must open automatically."""
        from unittest.mock import patch
        from pathlib import Path as _Path
        from fsmodmanager.core.model.settings import Settings as _Settings
        from fsmodmanager.core.service.collection_service import CollectionService
        from fsmodmanager.core.service.config_service import ConfigService
        from fsmodmanager.core.service.link_service import LinkService
        from fsmodmanager.core.service.settings_service import SettingsService
        from fsmodmanager.gui.main_window import MainWindow
        from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel

        source = tmp_path / "mods"
        collection = tmp_path / "collection"
        source.mkdir(); collection.mkdir()
        data_dir = tmp_path / "data"   # settings.json does NOT exist here

        # Build the settings object the dialog would return after user clicks OK
        confirmed = _Settings(
            source_mod_folder=str(source),
            mod_collection_folder=str(collection),
            savegame_path=str(tmp_path),
            # Avoids the blocking "Konfigurationen aus Savegames erstellen?"
            # QMessageBox that _do_initialize() would otherwise show – nothing
            # answers it in a headless test, so it would hang forever.
            savegames_read=True,
        )

        vm = MainViewModel(
            settings_service=SettingsService(data_dir=data_dir),
            config_service=ConfigService(configs_dir=tmp_path / "configs"),
            link_service=LinkService(),
            collection_service=CollectionService(),
            configs_dir_factory=lambda s: _Path(s.mod_collection_folder).parent / "LS_sg_config",
        )
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)

        dialog_shown = []

        def fake_exec(self_dialog):
            dialog_shown.append(self_dialog)
            self_dialog.settings = confirmed
            return True  # simulate OK

        with patch("fsmodmanager.gui.main_window.SettingsDialog.exec", fake_exec):
            with qtbot.waitSignal(vm.available_mods_changed, timeout=2000):
                window.show()

        assert dialog_shown, "SettingsDialog was not shown on first run"

    def test_window_opens_and_shows_mods(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        assert window._available_list.list_model.rowCount() == 3

    def test_move_all_right_button(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        window._btn_move_all_right.click()
        assert window._selected_list.list_model.rowCount() == 3
        assert window._available_list.list_model.rowCount() == 0

    def test_move_all_left_button(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        window._btn_move_all_right.click()
        window._btn_move_all_left.click()
        assert window._available_list.list_model.rowCount() == 3
        assert window._selected_list.list_model.rowCount() == 0

    def test_new_config_appears_in_combo(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        with _patch_new_config_dialog("Hof1"):
            window._btn_new.click()
        assert window._config_combo.findText("Hof1") >= 0

    def test_status_updated_after_save(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        with _patch_new_config_dialog("Hof2"):
            window._btn_new.click()
        window._btn_save.click()
        assert window._status_label.text() == "Gespeichert"

    def test_error_dialog_shown_on_link_error(self, fs, qtbot, monkeypatch) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        from fsmodmanager.core.service.link_service import LinkError, LinkService

        # Put ZIPs in collection directly so collect() is a no-op during init.
        col = fs / "collection"
        _make_mod_zip(col, "FS25_LinkTest.zip", "Link Test")

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        # _btn_activate stays disabled without an active config (see
        # MainWindow._on_active_config_changed) — select one first.
        vm.create_config("Hof1")
        vm.select_config("Hof1")

        monkeypatch.setattr(
            LinkService, "activate",
            lambda *a, **kw: (_ for _ in ()).throw(
                LinkError("Fehler: Symlink konnte nicht erstellt werden (Developer Mode?)")
            ),
        )
        window._btn_move_all_right.click()

        shown = []
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QMessageBox.critical",
            lambda *a, **kw: shown.append(a[2]) or None,
        )
        window._btn_activate.click()
        assert shown, "Error dialog was not shown"

    def test_new_mods_highlighted_in_both_lists(self, fs, qtbot) -> None:
        """A newly collected mod's highlight must not disappear when the mod
        moves between "Verfügbar" and "Ausgewählt" - only main_window.py
        knows about both ModListWidgets, so this can't be checked at the
        ViewModel level. Mirrors Java's existingModsTV/selectedModsTV row
        factories, which both check the same newMods set.
        """
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        expected = {"FS25_ModA.zip", "FS25_ModB.zip", "FS25_ModC.zip"}
        assert window._available_list.list_model._highlighted == expected

        window._btn_move_all_right.click()
        assert window._selected_list.list_model._highlighted == expected

    def test_new_mods_dialog_is_skipped_without_configurations(self, fs, qtbot, monkeypatch) -> None:
        """Nothing to assign new mods *to* – the dialog must not appear at all
        (it would be a modal dead end on a genuinely first run)."""
        from fsmodmanager.gui.main_window import MainWindow

        shown = []
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.NewModsAssignDialog.exec",
            lambda self_dialog: shown.append(True) or 0,
        )
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        assert not shown

    def test_new_mods_dialog_writes_the_chosen_assignments(self, fs, qtbot, monkeypatch) -> None:
        """The whole point of the dialog: several new mods land in several
        configs in one pass, driven here by its "alle zu allen" button."""
        from PySide6.QtWidgets import QDialog

        from fsmodmanager.core.model.configuration import Configuration
        from fsmodmanager.gui.main_window import MainWindow

        cfg_svc = ConfigService(configs_dir=fs / "configs")
        cfg_svc.save(Configuration(name="Alpha", mod_filenames=[]))
        cfg_svc.save(Configuration(name="Beta", mod_filenames=["FS25_ModA.zip"]))

        def accept_all(self_dialog):
            self_dialog._btn_all.click()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.NewModsAssignDialog.exec", accept_all
        )

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        expected = ["FS25_ModA.zip", "FS25_ModB.zip", "FS25_ModC.zip"]
        assert sorted(cfg_svc.load("Alpha").mod_filenames) == expected
        # Beta already listed ModA – it must not end up in there twice.
        assert sorted(cfg_svc.load("Beta").mod_filenames) == expected

    def test_new_mods_dialog_offers_only_readable_mods(self, fs, qtbot, monkeypatch) -> None:
        """collect() moves every .zip, but an unreadable one never becomes a
        Mod - offering it would write a filename into configs that the mod
        lists can never show."""
        from fsmodmanager.core.model.configuration import Configuration
        from fsmodmanager.gui.main_window import MainWindow

        (fs / "mods" / "FS25_Broken.zip").write_bytes(b"not a zip at all")
        ConfigService(configs_dir=fs / "configs").save(
            Configuration(name="Alpha", mod_filenames=[])
        )

        offered = []
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.NewModsAssignDialog.exec",
            lambda self_dialog: offered.extend(m.filename for m in self_dialog._mods) or 0,
        )

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        assert offered == ["FS25_ModA.zip", "FS25_ModB.zip", "FS25_ModC.zip"]

    def test_profile_button_lists_every_installation(self, two_games, qtbot) -> None:
        window, _vm = two_games
        assert window._btn_profile.text() == "Spiel: FS25"
        assert window.windowTitle() == "FS Mod Manager – FS25"
        labels = [a.text() for a in window._profile_menu.actions() if a.text()]
        assert labels[:2] == ["FS25", "FS22"]
        assert "Neue Spielversion…" in labels

    def test_active_profile_is_checked_in_the_menu(self, two_games, qtbot) -> None:
        window, _vm = two_games
        checked = [a.text() for a in window._profile_menu.actions() if a.isChecked()]
        assert checked == ["FS25"]

    def test_menu_entry_switches_the_whole_window(self, two_games, qtbot) -> None:
        """Clicking the other installation must swap mod lists, button and
        title together - a half-switched window is how you activate mods in
        the wrong game."""
        window, vm = two_games
        assert window._available_list.list_model.rowCount() == 1

        action = next(a for a in window._profile_menu.actions() if a.text() == "FS22")
        action.trigger()

        assert vm.settings.mod_collection_folder.endswith("fs22/collection")
        assert window._btn_profile.text() == "Spiel: FS22"
        assert window.windowTitle() == "FS Mod Manager – FS22"
        assert window._available_list.list_model.rowCount() == 1
        assert vm.available_mods[0].filename == "FS22_Only.zip"

    def test_switch_offers_the_new_installations_new_mods(self, two_games, qtbot, monkeypatch) -> None:
        """A profile switch runs the same startup flow as launching the app,
        so the other game's freshly collected mods get offered too."""
        from fsmodmanager.core.model.configuration import Configuration

        window, vm = two_games
        tmp = Path(vm.settings.savegame_path).parent
        _make_mod_zip(tmp / "fs22/mods", "FS22_Neu.zip", "Neu in FS22")
        ConfigService(configs_dir=tmp / "fs22/configs").save(
            Configuration(name="FS22-Config", mod_filenames=[])
        )

        offered = []
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.NewModsAssignDialog.exec",
            lambda self_dialog: offered.extend(m.filename for m in self_dialog._mods) or 0,
        )
        window._on_switch_profile("FS22")

        assert offered == ["FS22_Neu.zip"]

    def test_new_profile_is_added_and_switched_to(self, two_games, qtbot, monkeypatch) -> None:
        from PySide6.QtWidgets import QDialog, QMessageBox

        window, vm = two_games
        tmp = Path(vm.settings.savegame_path).parent
        for sub in ("fs19/mods", "fs19/collection"):
            (tmp / sub).mkdir(parents=True)

        def fill_and_accept(self_dialog):
            self_dialog._edit_name.setText("FS19")
            self_dialog._edit_source.setText(str(tmp / "fs19/mods"))
            self_dialog._edit_collection.setText(str(tmp / "fs19/collection"))
            self_dialog._edit_savegame.setText(str(tmp / "fs19"))
            self_dialog._on_accept()
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.ProfileEditDialog.exec", fill_and_accept
        )
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QMessageBox.question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )

        window._on_new_profile()

        assert vm.profile_names == ["FS25", "FS22", "FS19"]
        assert window._btn_profile.text() == "Spiel: FS19"

    def test_delete_removes_the_entry_but_no_files(self, two_games, qtbot, monkeypatch) -> None:
        from PySide6.QtWidgets import QMessageBox

        window, vm = two_games
        tmp = Path(vm.settings.savegame_path).parent
        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QMessageBox.question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )

        window._on_delete_profile("FS22")

        assert vm.profile_names == ["FS25"]
        assert (tmp / "fs22/collection/FS22_Only.zip").exists()
        assert [a.text() for a in window._profile_menu.actions() if a.isCheckable()] == ["FS25"]

    def test_settings_dialog_opens(self, fs, qtbot) -> None:
        from fsmodmanager.gui.main_window import MainWindow
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)
        from fsmodmanager.gui.dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(vm.settings, parent=window)
        qtbot.addWidget(dialog)
        assert dialog._edit_source.text() == str(fs / "mods")
        assert dialog._edit_collection.text() == str(fs / "collection")

    def test_rename_mod_via_context_menu_action(self, fs, qtbot, monkeypatch) -> None:
        """_on_rename_mod() drives QInputDialog for the corrected name and,
        with no conflict, applies it straight through to the ViewModel."""
        from fsmodmanager.gui.main_window import MainWindow

        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        # Collecting the invalid-name mod fires vm.warning_occurred, which
        # MainWindow shows as a real modal QMessageBox - stub it out so init
        # doesn't block on a dialog nothing will click.
        monkeypatch.setattr("fsmodmanager.gui.main_window.QMessageBox.warning", lambda *a, **kw: None)
        _show_and_init(window, vm, qtbot)

        mod = next(m for m in window._available_list.list_model.mods()
                   if m.filename == "FS25_Broken (1).zip")

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QInputDialog.getText",
            lambda *a, **kw: ("FS25_Broken.zip", True),
        )
        window._on_rename_mod(mod)

        filenames = {m.filename for m in window._available_list.list_model.mods()}
        assert "FS25_Broken.zip" in filenames
        assert "FS25_Broken (1).zip" not in filenames

    def test_rename_mod_cancelled_leaves_mod_untouched(self, fs, qtbot, monkeypatch) -> None:
        from fsmodmanager.gui.main_window import MainWindow

        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        monkeypatch.setattr("fsmodmanager.gui.main_window.QMessageBox.warning", lambda *a, **kw: None)
        _show_and_init(window, vm, qtbot)

        mod = next(m for m in window._available_list.list_model.mods()
                   if m.filename == "FS25_Broken (1).zip")

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QInputDialog.getText",
            lambda *a, **kw: ("", False),  # user hit Cancel
        )
        window._on_rename_mod(mod)

        filenames = {m.filename for m in window._available_list.list_model.mods()}
        assert "FS25_Broken (1).zip" in filenames

    def test_context_menu_offers_rename_only_for_invalid_names(self, fs, qtbot) -> None:
        """_build_mod_context_menu() is exercised directly (not via
        _on_mod_context_menu -> QMenu.exec()) since QMenu.exec() opens a
        real modal event loop under PySide6 that can't be reliably patched
        out and would hang the test."""
        from fsmodmanager.gui.main_window import MainWindow

        vm = _make_vm(fs)  # fixture mods all have valid names
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        mod = window._available_list.list_model.mods()[0]
        assert not mod.has_invalid_name
        actions = [a.text() for a in window._build_mod_context_menu(mod).actions()]

        assert "Datei richtig benennen…" not in actions
        assert "Löschen…" in actions

    def test_context_menu_offers_rename_for_invalid_names(self, fs, qtbot, monkeypatch) -> None:
        from fsmodmanager.gui.main_window import MainWindow

        source = fs / "mods"
        _make_mod_zip(source, "FS25_Broken (1).zip", "Broken")
        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        monkeypatch.setattr("fsmodmanager.gui.main_window.QMessageBox.warning", lambda *a, **kw: None)
        _show_and_init(window, vm, qtbot)

        mod = next(m for m in window._available_list.list_model.mods()
                   if m.filename == "FS25_Broken (1).zip")
        actions = [a.text() for a in window._build_mod_context_menu(mod).actions()]

        assert "Datei richtig benennen…" in actions
        assert "Löschen…" in actions

    def test_delete_mod_confirmed(self, fs, qtbot, monkeypatch) -> None:
        from fsmodmanager.gui.main_window import MainWindow

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        mod = next(m for m in window._available_list.list_model.mods()
                   if m.filename == "FS25_ModA.zip")

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QMessageBox.question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        window._on_delete_mod(mod)

        filenames = {m.filename for m in window._available_list.list_model.mods()}
        assert "FS25_ModA.zip" not in filenames
        assert not (fs / "collection" / "FS25_ModA.zip").exists()

    def test_delete_mod_cancelled_leaves_file_untouched(self, fs, qtbot, monkeypatch) -> None:
        from fsmodmanager.gui.main_window import MainWindow

        vm = _make_vm(fs)
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        _show_and_init(window, vm, qtbot)

        mod = next(m for m in window._available_list.list_model.mods()
                   if m.filename == "FS25_ModA.zip")

        monkeypatch.setattr(
            "fsmodmanager.gui.main_window.QMessageBox.question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        window._on_delete_mod(mod)

        filenames = {m.filename for m in window._available_list.list_model.mods()}
        assert "FS25_ModA.zip" in filenames
        assert (fs / "collection" / "FS25_ModA.zip").exists()
