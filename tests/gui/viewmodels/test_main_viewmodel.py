"""Tests for MainViewModel.

Uses pytest-qt's qtbot fixture to handle QApplication lifecycle and
to capture Qt signal emissions.
"""
import zipfile
from pathlib import Path

import pytest

from fsmodmanager.core.model.configuration import Configuration
from fsmodmanager.core.model.mod import Mod
from fsmodmanager.core.model.settings import Settings
from fsmodmanager.core.service.collection_service import CollectionService
from fsmodmanager.core.service.config_service import ConfigService
from fsmodmanager.core.service.link_service import LinkService
from fsmodmanager.core.service.settings_service import SettingsService
from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOD_DESC = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<modDesc descVersion="72">
    <author>Tester</author>
    <version>1.0.0.0</version>
    <title><en>{title}</en></title>
    <iconFilename>icon.dds</iconFilename>{maps}
</modDesc>"""

_MAPS_ELEMENT = """
    <maps>
        <map id="TestMap" className="Mission00" filename="$dataS/scripts/mission00.lua" configFilename="m.xml"/>
    </maps>"""


def _make_mod_zip(directory: Path, filename: str, title: str = "A Mod", is_map: bool = False) -> Path:
    path = directory / filename
    xml = _MOD_DESC.format(title=title, maps=_MAPS_ELEMENT if is_map else "")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("modDesc.xml", xml.encode())
    return path


def _make_vm(tmp_path: Path) -> MainViewModel:
    source = tmp_path / "mods"
    collection = tmp_path / "collection"
    source.mkdir()
    collection.mkdir()
    data_dir = tmp_path / "data"
    configs_dir = tmp_path / "configs"

    settings = Settings(
        source_mod_folder=str(source),
        mod_collection_folder=str(collection),
        savegame_path=str(tmp_path),
    )
    settings_svc = SettingsService(data_dir=data_dir)
    settings_svc.save(settings)

    return MainViewModel(
        settings_service=SettingsService(data_dir=data_dir),
        config_service=ConfigService(configs_dir=configs_dir),
        link_service=LinkService(),
        collection_service=CollectionService(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vm(tmp_path: Path, qtbot) -> MainViewModel:
    return _make_vm(tmp_path)


@pytest.fixture
def vm_with_mods(tmp_path: Path, qtbot) -> tuple[MainViewModel, Path]:
    vm = _make_vm(tmp_path)
    collection = tmp_path / "collection"
    _make_mod_zip(collection, "FS25_ModA.zip", "Mod A")
    _make_mod_zip(collection, "FS25_ModB.zip", "Mod B")
    vm.initialize()
    return vm, tmp_path


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInitialize:
    def test_loads_settings(self, vm: MainViewModel) -> None:
        vm.initialize()
        assert vm.settings is not None

    def test_scans_collection_folder(self, vm: MainViewModel, tmp_path: Path) -> None:
        _make_mod_zip(tmp_path / "collection", "FS25_ModA.zip")
        vm.initialize()
        assert len(vm.available_mods) == 1

    def test_available_mods_are_mod_instances(self, vm: MainViewModel, tmp_path: Path) -> None:
        _make_mod_zip(tmp_path / "collection", "FS25_ModA.zip")
        vm.initialize()
        assert all(isinstance(m, Mod) for m in vm.available_mods)

    def test_no_mods_means_empty_lists(self, vm: MainViewModel) -> None:
        vm.initialize()
        assert vm.available_mods == []
        assert vm.selected_mods == []


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class TestSignals:
    def test_available_mods_changed_emitted_on_init(
        self, vm: MainViewModel, tmp_path: Path, qtbot
    ) -> None:
        _make_mod_zip(tmp_path / "collection", "FS25_ModA.zip")
        with qtbot.waitSignal(vm.available_mods_changed, timeout=1000):
            vm.initialize()

    def test_config_names_changed_on_create(self, vm_with_mods, qtbot) -> None:
        vm, _ = vm_with_mods
        with qtbot.waitSignal(vm.config_names_changed, timeout=1000):
            vm.create_config("Hof1")

    def test_active_config_changed_on_select(self, vm_with_mods, qtbot) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Hof1")
        with qtbot.waitSignal(vm.active_config_changed, timeout=1000):
            vm.select_config("Hof1")

    def test_status_changed_on_save(self, vm_with_mods, qtbot) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        with qtbot.waitSignal(vm.status_changed, timeout=1000):
            vm.save_config()

    def test_error_occurred_on_link_permission_error(
        self, vm_with_mods, qtbot, monkeypatch
    ) -> None:
        vm, _ = vm_with_mods
        import os
        monkeypatch.setattr(os, "symlink", lambda *a, **kw: (_ for _ in ()).throw(PermissionError()))
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        with qtbot.waitSignal(vm.error_occurred, timeout=1000):
            vm.activate_config()


# ---------------------------------------------------------------------------
# Config operations
# ---------------------------------------------------------------------------

class TestConfigOperations:
    def test_create_config_appears_in_names(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Hof1")
        assert "Hof1" in vm._config_svc.list_names()

    def test_select_config_moves_mods_to_selected(self, vm_with_mods) -> None:
        vm, tmp_path = vm_with_mods
        vm.create_config("Hof1")
        vm.select_config("Hof1")
        vm.move_all_to_selected()
        vm.save_config()

        vm.select_config("Hof1")
        assert len(vm.selected_mods) == 2
        assert len(vm.available_mods) == 0

    def test_select_nonexistent_config_clears_selection(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.select_config("DoesNotExist")
        assert vm.selected_mods == []
        assert vm.active_config_name == ""

    def test_delete_config(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Hof1")
        vm.delete_config("Hof1")
        assert not vm._config_svc.exists("Hof1")

    def test_copy_config(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Original")
        vm.copy_config("Original", "Kopie")
        assert vm._config_svc.exists("Kopie")

    def test_rename_config(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alt")
        vm.rename_config("Alt", "Neu")
        assert vm._config_svc.exists("Neu")
        assert not vm._config_svc.exists("Alt")

    def test_rename_active_config_updates_active_name(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alt")
        vm.select_config("Alt")
        vm.rename_config("Alt", "Neu")
        assert vm.active_config_name == "Neu"


# ---------------------------------------------------------------------------
# Mod list manipulation
# ---------------------------------------------------------------------------

class TestModMovement:
    def test_move_to_selected(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        mod = vm.available_mods[0]
        vm.move_to_selected([mod])
        assert mod.filename in [m.filename for m in vm.selected_mods]
        assert mod.filename not in [m.filename for m in vm.available_mods]

    def test_move_to_available(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.move_all_to_selected()
        mod = vm.selected_mods[0]
        vm.move_to_available([mod])
        assert mod.filename in [m.filename for m in vm.available_mods]

    def test_move_all_to_selected(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.move_all_to_selected()
        assert len(vm.available_mods) == 0
        assert len(vm.selected_mods) == 2

    def test_move_all_to_available(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.move_all_to_selected()
        vm.move_all_to_available()
        assert len(vm.selected_mods) == 0
        assert len(vm.available_mods) == 2


# ---------------------------------------------------------------------------
# Savegame import
# ---------------------------------------------------------------------------

class TestSavegameImport:
    def test_import_creates_config(self, vm_with_mods, tmp_path: Path) -> None:
        vm, _ = vm_with_mods
        sg_dir = tmp_path / "savegame1"
        sg_dir.mkdir()
        xml = sg_dir / "careerSavegame.xml"
        xml.write_text(
            '<?xml version="1.0"?><careerSavegame>'
            '<mod modName="FS25_ModA" title="A" version="1.0" required="false" fileHash="x"/>'
            "</careerSavegame>",
            encoding="utf-8",
        )
        vm.import_savegame(xml)
        assert vm._config_svc.exists("savegame1")

    def test_import_selects_config(self, vm_with_mods, tmp_path: Path) -> None:
        vm, _ = vm_with_mods
        sg_dir = tmp_path / "savegame2"
        sg_dir.mkdir()
        xml = sg_dir / "careerSavegame.xml"
        xml.write_text(
            '<?xml version="1.0"?><careerSavegame>'
            '<mod modName="FS25_ModA" title="A" version="1.0" required="false" fileHash="x"/>'
            "</careerSavegame>",
            encoding="utf-8",
        )
        vm.import_savegame(xml)
        assert vm.active_config_name == "savegame2"


# ---------------------------------------------------------------------------
# Export (new feature, no Java equivalent)
# ---------------------------------------------------------------------------

class TestExportSelectedMods:
    def test_bundles_selected_mods_into_zip(self, vm_with_mods, tmp_path: Path, qtbot) -> None:
        import zipfile

        vm, _ = vm_with_mods
        mod_a = next(m for m in vm.available_mods if m.filename == "FS25_ModA.zip")
        vm.move_to_selected([mod_a])

        target = tmp_path / "export" / "bundle.zip"
        with qtbot.waitSignal(vm.status_changed, timeout=1000):
            vm.export_selected_mods(target)

        assert target.exists()
        with zipfile.ZipFile(target) as out:
            assert out.namelist() == ["FS25_ModA.zip"]

    def test_empty_selection_emits_warning_and_writes_nothing(
        self, vm_with_mods, tmp_path: Path, qtbot
    ) -> None:
        vm, _ = vm_with_mods
        target = tmp_path / "bundle.zip"

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000):
            vm.export_selected_mods(target)

        assert not target.exists()

    def test_missing_source_zip_reported_as_warning_but_still_exports(
        self, vm_with_mods, tmp_path: Path, qtbot
    ) -> None:
        import zipfile

        vm, root = vm_with_mods
        mod_a = next(m for m in vm.available_mods if m.filename == "FS25_ModA.zip")
        mod_b = next(m for m in vm.available_mods if m.filename == "FS25_ModB.zip")
        vm.move_to_selected([mod_a, mod_b])

        # Simulate ModB's ZIP having disappeared from the collection folder
        # after it was already loaded into the selection.
        (root / "collection" / "FS25_ModB.zip").unlink()

        target = tmp_path / "bundle.zip"
        with qtbot.waitSignal(vm.warning_occurred, timeout=1000) as blocker:
            vm.export_selected_mods(target)

        assert "FS25_ModB.zip" in blocker.args[0]
        with zipfile.ZipFile(target) as out:
            assert out.namelist() == ["FS25_ModA.zip"]


# ---------------------------------------------------------------------------
# Single active map enforcement (new feature, no Java equivalent)
# ---------------------------------------------------------------------------

@pytest.fixture
def vm_with_two_maps(tmp_path: Path, qtbot) -> tuple[MainViewModel, Path]:
    """Two map mods + one regular mod, all sitting in "available"."""
    vm = _make_vm(tmp_path)
    collection = tmp_path / "collection"
    _make_mod_zip(collection, "FS25_MapA.zip", "Map A", is_map=True)
    _make_mod_zip(collection, "FS25_MapB.zip", "Map B", is_map=True)
    _make_mod_zip(collection, "FS25_Regular.zip", "Regular Mod")
    vm.initialize()
    return vm, tmp_path


class TestSingleActiveMap:
    def test_second_map_swaps_out_the_first(self, vm_with_two_maps, qtbot) -> None:
        vm, _ = vm_with_two_maps
        map_a = next(m for m in vm.available_mods if m.filename == "FS25_MapA.zip")
        map_b = next(m for m in vm.available_mods if m.filename == "FS25_MapB.zip")

        vm.move_to_selected([map_a])
        assert [m.filename for m in vm.selected_mods] == ["FS25_MapA.zip"]

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000) as blocker:
            vm.move_to_selected([map_b])

        assert [m.filename for m in vm.selected_mods] == ["FS25_MapB.zip"]
        assert "FS25_MapA.zip" in [m.filename for m in vm.available_mods]
        assert "Map A" in blocker.args[0]
        assert "Map B" in blocker.args[0]

    def test_selecting_both_maps_at_once_keeps_only_the_last(
        self, vm_with_two_maps, qtbot
    ) -> None:
        vm, _ = vm_with_two_maps
        map_a = next(m for m in vm.available_mods if m.filename == "FS25_MapA.zip")
        map_b = next(m for m in vm.available_mods if m.filename == "FS25_MapB.zip")

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000):
            vm.move_to_selected([map_a, map_b])

        assert [m.filename for m in vm.selected_mods] == ["FS25_MapB.zip"]
        assert "FS25_MapA.zip" in [m.filename for m in vm.available_mods]

    def test_non_map_mods_unaffected_alongside_a_map(
        self, vm_with_two_maps, qtbot
    ) -> None:
        vm, _ = vm_with_two_maps
        map_a = next(m for m in vm.available_mods if m.filename == "FS25_MapA.zip")
        regular = next(m for m in vm.available_mods if m.filename == "FS25_Regular.zip")

        vm.move_to_selected([map_a, regular])

        selected = {m.filename for m in vm.selected_mods}
        assert selected == {"FS25_MapA.zip", "FS25_Regular.zip"}

    def test_move_all_to_selected_keeps_only_one_map(
        self, vm_with_two_maps, qtbot
    ) -> None:
        vm, _ = vm_with_two_maps

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000):
            vm.move_all_to_selected()

        map_filenames = [m.filename for m in vm.selected_mods if m.is_map]
        assert len(map_filenames) == 1
        # The bounced map must land back in "available", not vanish.
        assert vm.available_mods and all(m.is_map for m in vm.available_mods)

    def test_no_warning_when_only_one_map_selected(
        self, vm_with_two_maps, qtbot
    ) -> None:
        vm, _ = vm_with_two_maps
        map_a = next(m for m in vm.available_mods if m.filename == "FS25_MapA.zip")

        received = []
        vm.warning_occurred.connect(received.append)
        vm.move_to_selected([map_a])

        assert received == []
        assert [m.filename for m in vm.selected_mods] == ["FS25_MapA.zip"]

    def test_select_config_with_two_maps_keeps_only_one(
        self, vm_with_two_maps, qtbot
    ) -> None:
        """Defends against a legacy/hand-edited config JSON that lists two
        maps - select_config() must not leave the invariant violated."""
        vm, _ = vm_with_two_maps
        vm.create_config("BadConfig")
        vm._config_svc.save(
            Configuration(
                name="BadConfig",
                mod_filenames=["FS25_MapA.zip", "FS25_MapB.zip", "FS25_Regular.zip"],
            )
        )

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000):
            vm.select_config("BadConfig")

        map_filenames = [m.filename for m in vm.selected_mods if m.is_map]
        assert len(map_filenames) == 1
        assert "FS25_Regular.zip" in [m.filename for m in vm.selected_mods]

    def test_activate_refuses_when_two_maps_selected(
        self, vm_with_two_maps, qtbot, monkeypatch
    ) -> None:
        """Safety net at activation time, bypassing the normal move methods
        entirely to simulate the invariant somehow being violated anyway."""
        vm, _ = vm_with_two_maps
        map_a = next(m for m in vm.available_mods if m.filename == "FS25_MapA.zip")
        map_b = next(m for m in vm.available_mods if m.filename == "FS25_MapB.zip")
        vm._selected_mods = [map_a, map_b]  # bypass _enforce_single_active_map()

        activated = []
        monkeypatch.setattr(
            "fsmodmanager.gui.viewmodels.main_viewmodel.LinkService.activate",
            lambda *a, **kw: activated.append(True),
        )

        with qtbot.waitSignal(vm.error_occurred, timeout=1000) as blocker:
            vm.activate_config()

        assert not activated, "LinkService.activate must not be called with two maps selected"
        assert "Map A" in blocker.args[0]
        assert "Map B" in blocker.args[0]

    def test_multiple_regular_mods_never_bounced(self, vm_with_mods, qtbot) -> None:
        """Sanity/no-regression check: the single-map rule must not affect
        plain (non-map) mods at all."""
        vm, _ = vm_with_mods
        received = []
        vm.warning_occurred.connect(received.append)
        vm.move_all_to_selected()

        assert received == []
        assert {m.filename for m in vm.selected_mods} == {"FS25_ModA.zip", "FS25_ModB.zip"}
