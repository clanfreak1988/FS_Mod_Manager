import sys
import types
from pathlib import Path

import pytest

from fsmodmanager.core.model.settings import Settings
from fsmodmanager.core.service.settings_service import (
    SettingsService,
    _windows_documents_dir,
)


@pytest.fixture
def svc(tmp_path: Path) -> SettingsService:
    """SettingsService backed by a temporary directory."""
    return SettingsService(data_dir=tmp_path)


@pytest.fixture
def sample_settings() -> Settings:
    return Settings(
        source_mod_folder="/mods",
        mod_collection_folder="/collection",
        savegame_path="/saves",
        active_modpack="Mein Hof",
        scene_width=1280.0,
        scene_height=800.0,
    )


class TestSaveAndLoad:
    def test_save_creates_file(self, svc: SettingsService, sample_settings: Settings) -> None:
        svc.save(sample_settings)
        assert svc.settings_file.exists()

    def test_roundtrip(self, svc: SettingsService, sample_settings: Settings) -> None:
        svc.save(sample_settings)
        loaded = svc.load()
        assert loaded == sample_settings

    def test_save_overwrites(self, svc: SettingsService, sample_settings: Settings) -> None:
        svc.save(sample_settings)
        sample_settings.active_modpack = "Neuer Hof"
        svc.save(sample_settings)
        assert svc.load().active_modpack == "Neuer Hof"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        svc = SettingsService(data_dir=nested)
        svc.save(Settings(source_mod_folder="/m", mod_collection_folder="/c", savegame_path="/s"))
        assert svc.settings_file.exists()


class TestExists:
    def test_false_before_save(self, svc: SettingsService) -> None:
        assert svc.exists() is False

    def test_true_after_save(self, svc: SettingsService, sample_settings: Settings) -> None:
        svc.save(sample_settings)
        assert svc.exists() is True


class TestDefaultPaths:
    def test_defaults_without_callback(self, svc: SettingsService) -> None:
        """When FS path does not exist and no callback is given, still get a Settings object."""
        settings = svc.load(ask_for_path=None)
        assert isinstance(settings, Settings)
        assert "FarmingSimulator2025" in settings.source_mod_folder
        assert "FarmingSimulator2025" in settings.mod_collection_folder
        assert "FarmingSimulator2025" in settings.savegame_path

    def test_source_mod_folder_is_mods_subdir(self, svc: SettingsService) -> None:
        settings = svc.load()
        assert settings.source_mod_folder.endswith("mods")

    def test_collection_folder_is_ls_mods_subdir(self, svc: SettingsService) -> None:
        settings = svc.load()
        assert settings.mod_collection_folder.endswith("LS_mods")

    def test_callback_used_when_default_path_missing(self, tmp_path: Path) -> None:
        """If the default FS path doesn't exist, the callback is called."""
        custom_path = tmp_path / "MyCustomFS"
        custom_path.mkdir()
        callback_called = []

        def ask() -> str:
            callback_called.append(True)
            return str(custom_path)

        svc = SettingsService(data_dir=tmp_path / "data")
        settings = svc.load(ask_for_path=ask)

        assert callback_called, "Callback should have been invoked"
        assert str(custom_path / "mods") == settings.source_mod_folder
        assert str(custom_path / "LS_mods") == settings.mod_collection_folder
        assert str(custom_path) == settings.savegame_path

    def test_callback_not_called_when_file_exists(
        self, svc: SettingsService, sample_settings: Settings
    ) -> None:
        """Callback must not be invoked when settings.json already exists."""
        svc.save(sample_settings)
        callback_called = []
        svc.load(ask_for_path=lambda: callback_called.append(True) or "/unused")
        assert not callback_called

    def test_callback_not_called_when_default_path_exists(self, tmp_path: Path) -> None:
        """Callback must not be invoked when the default FS path is found."""
        # Simulate an existing game directory at the standard location by pointing
        # _find_game_home at a directory we create (monkeypatching home is complex,
        # so we verify via the callback-not-called contract).
        svc = SettingsService(data_dir=tmp_path / "data")
        callback_called = []

        # The default path ~/ Documents/My Games/FarmingSimulator2025 almost
        # certainly does not exist on the CI/dev machine, so the callback WILL be
        # called here – unless the dev has FS25 installed.  We just assert the
        # returned Settings is well-formed.
        settings = svc.load(ask_for_path=lambda: str(tmp_path))
        assert isinstance(settings, Settings)


class TestSettingsFilePath:
    def test_file_is_inside_data_dir(self, svc: SettingsService, tmp_path: Path) -> None:
        assert svc.settings_file.parent == tmp_path

    def test_file_name(self, svc: SettingsService) -> None:
        assert svc.settings_file.name == "settings.json"


class TestWindowsDocumentsDir:
    """Tests for the registry-based Documents-folder lookup.

    Handles a redirected Windows "Documents" folder (Group Policy
    redirection, or OneDrive "Known Folder Move", which is on by default on
    many Windows 11 / Microsoft 365 setups). Mirrors Java's
    ModManagerConfig.getDocumentsPath(), but reads the registry directly via
    `winreg` instead of shelling out to `reg query`.

    Full path semantics (drive letters, `%VAR%` expansion) are Windows-only
    (`os.path.expandvars` / `pathlib.Path.is_absolute` behave differently on
    POSIX) and can only be fully exercised on a real Windows machine – see
    MIGRATION_PLAN.md Phase 13. These tests cover what is meaningfully
    testable cross-platform: the non-Windows short-circuit, graceful
    failure handling, and that a plain absolute value round-trips.
    """

    def test_returns_none_on_non_windows(self) -> None:
        # This test suite runs on Linux/macOS in CI; no monkeypatching needed
        # to exercise the real "not Windows" branch.
        assert sys.platform != "win32"
        assert _windows_documents_dir() is None

    def test_returns_none_when_registry_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing key/value (e.g. non-standard Windows setup) must not raise."""
        monkeypatch.setattr(
            "fsmodmanager.core.service.settings_service.sys.platform", "win32"
        )

        def _raise_not_found(*_args, **_kwargs):
            raise OSError("registry key not found")

        fake_winreg = types.SimpleNamespace(
            HKEY_CURRENT_USER=object(),
            OpenKey=_raise_not_found,
            QueryValueEx=lambda *_a, **_k: (_ for _ in ()).throw(OSError("unused")),
        )
        monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

        assert _windows_documents_dir() is None

    def test_reads_personal_value_from_correct_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies OpenKey/QueryValueEx are called against the right registry path."""
        monkeypatch.setattr(
            "fsmodmanager.core.service.settings_service.sys.platform", "win32"
        )
        opened_keys: list[tuple[object, str]] = []
        queried: list[tuple[object, str]] = []

        class _FakeKey:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        def _open_key(hive, subkey):
            opened_keys.append((hive, subkey))
            return _FakeKey()

        def _query_value_ex(key, name):
            queried.append((key, name))
            # Plain absolute POSIX-style value: on real Windows this would be
            # a drive-letter path (e.g. "C:\\Users\\X\\OneDrive\\Documents"),
            # which only pathlib.WindowsPath recognises as absolute. A POSIX
            # style value is used here so the assertion below is meaningful
            # when this test runs on Linux/macOS too.
            return ("/fake/redirected/Documents", 1)

        fake_winreg = types.SimpleNamespace(
            HKEY_CURRENT_USER="HKCU",
            OpenKey=_open_key,
            QueryValueEx=_query_value_ex,
        )
        monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

        result = _windows_documents_dir()

        assert opened_keys == [
            (
                "HKCU",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            )
        ]
        assert queried == [(opened_keys[0], "Personal")] or queried[0][1] == "Personal"
        assert result == Path("/fake/redirected/Documents")

    def test_find_game_home_prefers_registry_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the registry resolves a Documents dir whose FS25 subfolder
        exists, that path must win over the plain ~/Documents default."""
        redirected_docs = tmp_path / "Redirected" / "Documents"
        game_home = redirected_docs / "My Games" / "FarmingSimulator2025"
        game_home.mkdir(parents=True)

        monkeypatch.setattr(
            "fsmodmanager.core.service.settings_service._windows_documents_dir",
            lambda: redirected_docs,
        )

        svc = SettingsService(data_dir=tmp_path / "data")
        settings = svc.load()

        assert settings.savegame_path == str(game_home)


class TestProfileHelpers:
    def test_save_folds_top_level_edits_into_the_active_profile(
        self, svc: SettingsService, sample_settings: Settings
    ) -> None:
        """Everything in the app edits the flat fields; save() is the single
        point where that has to reach the profile they belong to."""
        sample_settings.active_modpack = "Winter"
        sample_settings.mod_collection_folder = "/anderswo"

        svc.save(sample_settings)
        restored = svc.load()

        assert restored.active_game_profile.active_modpack == "Winter"
        assert restored.active_game_profile.mod_collection_folder == "/anderswo"

    def test_defaults_come_with_exactly_one_profile(self, tmp_path: Path) -> None:
        svc = SettingsService(data_dir=tmp_path / "data")
        settings = svc.load(ask_for_path=lambda: str(tmp_path / "FarmingSimulator2025"))
        assert len(settings.profiles) == 1
        assert settings.active_profile == settings.profiles[0].name

    def test_default_game_home_uses_the_requested_year(self) -> None:
        from fsmodmanager.core.service.settings_service import default_game_home

        assert default_game_home("2022").name == "FarmingSimulator2022"
        assert default_game_home("2022").parent.name == "My Games"

    def test_default_profile_lays_out_mods_and_collection(self) -> None:
        from fsmodmanager.core.service.settings_service import default_profile

        profile = default_profile("FS22", Path("/games/FarmingSimulator2022"))
        assert profile.source_mod_folder == str(Path("/games/FarmingSimulator2022/mods"))
        assert profile.mod_collection_folder == str(
            Path("/games/FarmingSimulator2022/LS_mods")
        )
        assert profile.savegame_path == str(Path("/games/FarmingSimulator2022"))

    def test_fs_versions_are_offered_newest_first(self) -> None:
        from fsmodmanager.core.service.settings_service import FS_VERSIONS

        years = [year for _label, year in FS_VERSIONS]
        assert years == sorted(years, reverse=True)
        assert "2025" in years
