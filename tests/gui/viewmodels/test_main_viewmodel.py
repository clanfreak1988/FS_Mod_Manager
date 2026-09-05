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


# ---------------------------------------------------------------------------
# Assigning newly collected mods to configurations
# ---------------------------------------------------------------------------

class TestAssignModsToConfigs:
    def test_adds_filenames_to_the_named_config(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")

        vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_ModA.zip"]

    def test_one_mod_can_be_added_to_several_configs(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")
        vm.create_config("Beta")

        vm.assign_mods_to_configs(
            {"Alpha": ["FS25_ModA.zip"], "Beta": ["FS25_ModA.zip"]}
        )

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_ModA.zip"]
        assert vm._config_svc.load("Beta").mod_filenames == ["FS25_ModA.zip"]

    def test_several_mods_can_be_added_to_one_config(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")

        vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip", "FS25_ModB.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == [
            "FS25_ModA.zip",
            "FS25_ModB.zip",
        ]

    def test_keeps_mods_the_config_already_had(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm._config_svc.save(Configuration(name="Alpha", mod_filenames=["FS25_Old.zip"]))

        vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip"]})

        assert set(vm._config_svc.load("Alpha").mod_filenames) == {
            "FS25_Old.zip",
            "FS25_ModA.zip",
        }

    def test_does_not_duplicate_an_already_listed_mod(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm._config_svc.save(Configuration(name="Alpha", mod_filenames=["FS25_ModA.zip"]))

        vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_ModA.zip"]

    def test_unknown_config_is_ignored(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods

        vm.assign_mods_to_configs({"DoesNotExist": ["FS25_ModA.zip"]})

        assert vm._config_svc.list_names() == []

    def test_empty_filename_list_writes_nothing(self, vm_with_mods) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")

        vm.assign_mods_to_configs({"Alpha": []})

        assert vm._config_svc.load("Alpha").mod_filenames == []

    def test_active_config_selection_is_refreshed(self, vm_with_mods) -> None:
        """Mods added to the *active* config must appear in the right-hand
        column right away, not only after the next select_config()."""
        vm, _ = vm_with_mods
        vm.create_config("Alpha")
        vm.select_config("Alpha")
        assert vm.selected_mods == []

        vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip"]})

        assert [m.filename for m in vm.selected_mods] == ["FS25_ModA.zip"]

    def test_inactive_config_does_not_disturb_the_current_selection(
        self, vm_with_mods
    ) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")
        vm.create_config("Beta")
        vm.select_config("Alpha")

        vm.assign_mods_to_configs({"Beta": ["FS25_ModA.zip"]})

        assert vm.selected_mods == []

    def test_emits_status_after_assigning(self, vm_with_mods, qtbot) -> None:
        vm, _ = vm_with_mods
        vm.create_config("Alpha")

        with qtbot.waitSignal(vm.status_changed, timeout=1000) as blocker:
            vm.assign_mods_to_configs({"Alpha": ["FS25_ModA.zip"]})

        assert "1 Konfiguration" in blocker.args[0]


class TestAssignMapsToConfigs:
    """A configuration must never end up holding two maps."""

    def _vm_with_map(self, tmp_path: Path) -> MainViewModel:
        vm = _make_vm(tmp_path)
        collection = tmp_path / "collection"
        _make_mod_zip(collection, "FS25_MapA.zip", "Map A", is_map=True)
        _make_mod_zip(collection, "FS25_MapB.zip", "Map B", is_map=True)
        _make_mod_zip(collection, "FS25_ModA.zip", "Mod A")
        vm.initialize()
        return vm

    def test_map_is_added_to_a_config_without_one(self, tmp_path, qtbot) -> None:
        vm = self._vm_with_map(tmp_path)
        vm.create_config("Alpha")

        vm.assign_mods_to_configs({"Alpha": ["FS25_MapA.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_MapA.zip"]

    def test_map_is_refused_when_the_config_already_has_one(self, tmp_path, qtbot) -> None:
        vm = self._vm_with_map(tmp_path)
        vm._config_svc.save(
            Configuration(name="Alpha", mod_filenames=["FS25_MapA.zip"])
        )

        vm.assign_mods_to_configs({"Alpha": ["FS25_MapB.zip", "FS25_ModA.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == [
            "FS25_MapA.zip",
            "FS25_ModA.zip",
        ]

    def test_only_the_first_of_two_new_maps_is_added(self, tmp_path, qtbot) -> None:
        vm = self._vm_with_map(tmp_path)
        vm.create_config("Alpha")

        vm.assign_mods_to_configs({"Alpha": ["FS25_MapA.zip", "FS25_MapB.zip"]})

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_MapA.zip"]

    def test_refused_map_triggers_a_warning_naming_map_and_config(
        self, tmp_path, qtbot
    ) -> None:
        vm = self._vm_with_map(tmp_path)
        vm._config_svc.save(
            Configuration(name="Alpha", mod_filenames=["FS25_MapA.zip"])
        )

        with qtbot.waitSignal(vm.warning_occurred, timeout=1000) as blocker:
            vm.assign_mods_to_configs({"Alpha": ["FS25_MapB.zip"]})

        assert "FS25_MapB.zip" in blocker.args[0]
        assert "Alpha" in blocker.args[0]

    def test_a_map_may_still_go_into_several_map_free_configs(
        self, tmp_path, qtbot
    ) -> None:
        vm = self._vm_with_map(tmp_path)
        vm.create_config("Alpha")
        vm.create_config("Beta")

        vm.assign_mods_to_configs(
            {"Alpha": ["FS25_MapA.zip"], "Beta": ["FS25_MapA.zip"]}
        )

        assert vm._config_svc.load("Alpha").mod_filenames == ["FS25_MapA.zip"]
        assert vm._config_svc.load("Beta").mod_filenames == ["FS25_MapA.zip"]


# ---------------------------------------------------------------------------
# Game profiles (several FS installations side by side)
# ---------------------------------------------------------------------------

def _make_multi_profile_vm(tmp_path: Path) -> MainViewModel:
    """VM with two fully separate FS installations, FS25 active.

    Each gets its own mods/collection folder and - via the configs_dir
    factory, exactly as main.py wires it - its own configuration directory
    next to that collection folder.
    """
    from fsmodmanager.core.model.game_profile import GameProfile

    for sub in ("fs25/mods", "fs25/collection", "fs22/mods", "fs22/collection"):
        (tmp_path / sub).mkdir(parents=True)
    _make_mod_zip(tmp_path / "fs25/collection", "FS25_Only.zip", "Nur in FS25")
    _make_mod_zip(tmp_path / "fs22/collection", "FS22_Only.zip", "Nur in FS22")

    def _profile(name: str, home: str) -> GameProfile:
        return GameProfile(
            name=name,
            source_mod_folder=str(tmp_path / home / "mods"),
            mod_collection_folder=str(tmp_path / home / "collection"),
            savegame_path=str(tmp_path / home),
            savegames_read=True,
        )

    data_dir = tmp_path / "data"
    settings = Settings(
        source_mod_folder=str(tmp_path / "fs25/mods"),
        mod_collection_folder=str(tmp_path / "fs25/collection"),
        savegame_path=str(tmp_path / "fs25"),
        savegames_read=True,
        profiles=[_profile("FS25", "fs25"), _profile("FS22", "fs22")],
        active_profile="FS25",
    )
    SettingsService(data_dir=data_dir).save(settings)

    vm = MainViewModel(
        settings_service=SettingsService(data_dir=data_dir),
        config_service=ConfigService(configs_dir=tmp_path / "placeholder"),
        link_service=LinkService(),
        collection_service=CollectionService(),
        configs_dir_factory=lambda s: Path(s.mod_collection_folder).parent / "configs",
    )
    vm.initialize()
    return vm


@pytest.fixture
def multi_vm(tmp_path: Path, qtbot) -> MainViewModel:
    return _make_multi_profile_vm(tmp_path)


class TestSwitchProfile:
    def test_paths_follow_the_new_profile(self, multi_vm: MainViewModel, tmp_path: Path) -> None:
        multi_vm.switch_profile("FS22")
        assert multi_vm.settings.mod_collection_folder == str(tmp_path / "fs22/collection")
        assert multi_vm.settings.source_mod_folder == str(tmp_path / "fs22/mods")

    def test_mod_list_shows_the_other_installation(self, multi_vm: MainViewModel) -> None:
        assert [m.filename for m in multi_vm.available_mods] == ["FS25_Only.zip"]
        multi_vm.switch_profile("FS22")
        assert [m.filename for m in multi_vm.available_mods] == ["FS22_Only.zip"]

    def test_configurations_are_separate_per_profile(self, multi_vm: MainViewModel) -> None:
        """The whole point of one collection folder per installation: the
        config JSONs live next to it, so they can't bleed across."""
        multi_vm.create_config("Nur FS25")
        multi_vm.switch_profile("FS22")
        assert multi_vm._config_svc.list_names() == []

        multi_vm.create_config("Nur FS22")
        multi_vm.switch_profile("FS25")
        assert multi_vm._config_svc.list_names() == ["Nur FS25"]

    def test_active_config_name_is_cleared(self, multi_vm: MainViewModel) -> None:
        """A config name belongs to the collection folder it was loaded from
        and must not survive into an installation that has no such config."""
        multi_vm.create_config("Nur FS25")
        multi_vm.select_config("Nur FS25")
        multi_vm.switch_profile("FS22")
        assert multi_vm.active_config_name == ""

    def test_emits_active_profile_changed(self, multi_vm: MainViewModel, qtbot) -> None:
        with qtbot.waitSignal(multi_vm.active_profile_changed, timeout=1000) as blocker:
            multi_vm.switch_profile("FS22")
        assert blocker.args[0] == "FS22"

    def test_switch_is_persisted(self, multi_vm: MainViewModel, tmp_path: Path) -> None:
        multi_vm.switch_profile("FS22")
        reloaded = SettingsService(data_dir=tmp_path / "data").load()
        assert reloaded.active_profile == "FS22"
        assert reloaded.mod_collection_folder == str(tmp_path / "fs22/collection")

    def test_each_profile_keeps_its_own_active_modpack(
        self, multi_vm: MainViewModel, tmp_path: Path
    ) -> None:
        multi_vm.settings.active_modpack = "Sommer"
        multi_vm.switch_profile("FS22")
        assert multi_vm.settings.active_modpack == ""

        multi_vm.switch_profile("FS25")
        assert multi_vm.settings.active_modpack == "Sommer"

    def test_switching_to_the_active_profile_does_nothing(
        self, multi_vm: MainViewModel
    ) -> None:
        received = []
        multi_vm.active_profile_changed.connect(received.append)
        multi_vm.switch_profile("FS25")
        assert received == []

    def test_unknown_profile_reports_an_error(self, multi_vm: MainViewModel, qtbot) -> None:
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000) as blocker:
            multi_vm.switch_profile("FS17")
        assert "FS17" in blocker.args[0]
        assert multi_vm.active_profile_name == "FS25"

    def test_missing_folders_are_reported(self, multi_vm: MainViewModel, tmp_path, qtbot) -> None:
        import shutil

        shutil.rmtree(tmp_path / "fs22/mods")
        with qtbot.waitSignal(multi_vm.warning_occurred, timeout=1000) as blocker:
            multi_vm.switch_profile("FS22")
        assert "Mod-Ordner" in blocker.args[0]


class TestManageProfiles:
    def _new(self, tmp_path: Path, name: str = "FS19", home: str = "fs19"):
        from fsmodmanager.core.model.game_profile import GameProfile

        (tmp_path / home / "mods").mkdir(parents=True, exist_ok=True)
        (tmp_path / home / "collection").mkdir(parents=True, exist_ok=True)
        return GameProfile(
            name=name,
            source_mod_folder=str(tmp_path / home / "mods"),
            mod_collection_folder=str(tmp_path / home / "collection"),
            savegame_path=str(tmp_path / home),
        )

    def test_add_appends_without_switching(self, multi_vm, tmp_path) -> None:
        assert multi_vm.add_profile(self._new(tmp_path)) is True
        assert multi_vm.profile_names == ["FS25", "FS22", "FS19"]
        assert multi_vm.active_profile_name == "FS25"

    def test_add_is_persisted(self, multi_vm, tmp_path) -> None:
        multi_vm.add_profile(self._new(tmp_path))
        reloaded = SettingsService(data_dir=tmp_path / "data").load()
        assert reloaded.profile_names == ["FS25", "FS22", "FS19"]

    def test_add_emits_profiles_changed(self, multi_vm, tmp_path, qtbot) -> None:
        with qtbot.waitSignal(multi_vm.profiles_changed, timeout=1000) as blocker:
            multi_vm.add_profile(self._new(tmp_path))
        assert blocker.args[0] == ["FS25", "FS22", "FS19"]

    def test_add_rejects_a_duplicate_name_ignoring_case(self, multi_vm, tmp_path, qtbot) -> None:
        profile = self._new(tmp_path, name="fs22")
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000):
            assert multi_vm.add_profile(profile) is False
        assert multi_vm.profile_names == ["FS25", "FS22"]

    def test_add_rejects_an_empty_name(self, multi_vm, tmp_path, qtbot) -> None:
        profile = self._new(tmp_path, name="   ")
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000):
            assert multi_vm.add_profile(profile) is False

    def test_add_rejects_a_shared_collection_folder(self, multi_vm, tmp_path, qtbot) -> None:
        """Two profiles on one collection folder would silently share their
        configurations, which live right next to it."""
        profile = self._new(tmp_path)
        profile.mod_collection_folder = str(tmp_path / "fs22/collection")
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000) as blocker:
            assert multi_vm.add_profile(profile) is False
        assert "FS22" in blocker.args[0]

    def test_add_rejects_a_shared_mod_folder(self, multi_vm, tmp_path, qtbot) -> None:
        profile = self._new(tmp_path)
        profile.source_mod_folder = str(tmp_path / "fs25/mods")
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000) as blocker:
            assert multi_vm.add_profile(profile) is False
        assert "FS25" in blocker.args[0]

    def test_update_renames_the_active_profile(self, multi_vm, tmp_path) -> None:
        edited = self._new(tmp_path, name="FS25 (Haupt)", home="fs25")
        assert multi_vm.update_active_profile(edited) is True
        assert multi_vm.profile_names == ["FS25 (Haupt)", "FS22"]
        assert multi_vm.active_profile_name == "FS25 (Haupt)"

    def test_update_keeps_per_profile_state(self, multi_vm, tmp_path) -> None:
        """savegames_read / active_modpack are state, not form fields - the
        edit dialog never shows them and must not reset them."""
        multi_vm.settings.active_modpack = "Sommer"
        multi_vm.settings.sync_active_profile()

        multi_vm.update_active_profile(self._new(tmp_path, name="Neu", home="fs25"))

        assert multi_vm.settings.active_game_profile.active_modpack == "Sommer"
        assert multi_vm.settings.active_game_profile.savegames_read is True

    def test_update_rejects_another_profiles_name(self, multi_vm, tmp_path, qtbot) -> None:
        edited = self._new(tmp_path, name="FS22", home="fs25")
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000):
            assert multi_vm.update_active_profile(edited) is False
        assert multi_vm.profile_names == ["FS25", "FS22"]

    def test_delete_removes_an_inactive_profile(self, multi_vm, tmp_path) -> None:
        assert multi_vm.delete_profile("FS22") is True
        assert multi_vm.profile_names == ["FS25"]
        reloaded = SettingsService(data_dir=tmp_path / "data").load()
        assert reloaded.profile_names == ["FS25"]

    def test_delete_leaves_the_files_alone(self, multi_vm, tmp_path) -> None:
        multi_vm.delete_profile("FS22")
        assert (tmp_path / "fs22/collection/FS22_Only.zip").exists()

    def test_delete_refuses_the_active_profile(self, multi_vm, qtbot) -> None:
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000) as blocker:
            assert multi_vm.delete_profile("FS25") is False
        assert "aktiv" in blocker.args[0]
        assert multi_vm.profile_names == ["FS25", "FS22"]

    def test_delete_of_an_unknown_profile_reports_an_error(self, multi_vm, qtbot) -> None:
        with qtbot.waitSignal(multi_vm.error_occurred, timeout=1000):
            assert multi_vm.delete_profile("FS17") is False
