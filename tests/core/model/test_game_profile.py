"""Tests for GameProfile and the profile handling inside Settings."""
import json

from fsmodmanager.core.model.game_profile import GameProfile, derive_profile_name
from fsmodmanager.core.model.settings import Settings


def _settings(**kwargs) -> Settings:
    base = dict(
        source_mod_folder="/games/FarmingSimulator2025/mods",
        mod_collection_folder="/games/FarmingSimulator2025/LS_mods",
        savegame_path="/games/FarmingSimulator2025",
    )
    base.update(kwargs)
    return Settings(**base)


def _profile(name: str, home: str) -> GameProfile:
    return GameProfile(
        name=name,
        source_mod_folder=f"{home}/mods",
        mod_collection_folder=f"{home}/LS_mods",
        savegame_path=home,
    )


class TestDeriveProfileName:
    def test_fs_folder_becomes_short_name(self) -> None:
        assert derive_profile_name("/home/u/Documents/My Games/FarmingSimulator2025") == "FS25"
        assert derive_profile_name("/home/u/Documents/My Games/FarmingSimulator2022") == "FS22"

    def test_unknown_folder_falls_back(self) -> None:
        assert derive_profile_name("/somewhere/else") == "Standard"


class TestSettingsMigration:
    def test_flat_settings_gain_a_profile(self) -> None:
        """A settings file written before profiles existed must come back as
        a single profile - otherwise the profile button has nothing to show."""
        s = _settings()
        assert s.profile_names == ["FS25"]
        assert s.active_profile == "FS25"

    def test_migrated_profile_keeps_the_original_paths(self) -> None:
        s = _settings()
        profile = s.active_game_profile
        assert profile.source_mod_folder == "/games/FarmingSimulator2025/mods"
        assert profile.mod_collection_folder == "/games/FarmingSimulator2025/LS_mods"
        assert profile.savegame_path == "/games/FarmingSimulator2025"

    def test_migrated_profile_takes_over_per_profile_state(self) -> None:
        s = _settings(savegames_read=True, active_modpack="Sommer")
        assert s.active_game_profile.savegames_read is True
        assert s.active_game_profile.active_modpack == "Sommer"

    def test_old_json_without_profiles_still_loads(self) -> None:
        raw = json.dumps({
            "source_mod_folder": "/games/FarmingSimulator2025/mods",
            "mod_collection_folder": "/games/FarmingSimulator2025/LS_mods",
            "savegame_path": "/games/FarmingSimulator2025",
            "savegames_read": True,
            "active_modpack": "Winter",
        })
        s = Settings.from_json(raw)
        assert s.profile_names == ["FS25"]
        assert s.active_game_profile.active_modpack == "Winter"

    def test_new_json_still_carries_the_flat_fields(self) -> None:
        """The mirrored top-level keys are what an older build reads; without
        them its Settings.from_dict() would raise a KeyError."""
        s = _settings(profiles=[_profile("FS22", "/games/FarmingSimulator2022")])
        data = json.loads(s.to_json())
        assert data["source_mod_folder"] == "/games/FarmingSimulator2022/mods"
        assert data["active_profile"] == "FS22"

    def test_unknown_active_profile_falls_back_to_the_first(self) -> None:
        s = _settings(
            profiles=[_profile("FS22", "/games/FarmingSimulator2022")],
            active_profile="Gibtsnicht",
        )
        assert s.active_profile == "FS22"
        assert s.source_mod_folder == "/games/FarmingSimulator2022/mods"


class TestApplyAndSync:
    def _two_profiles(self) -> Settings:
        return _settings(
            profiles=[
                _profile("FS25", "/games/FarmingSimulator2025"),
                _profile("FS22", "/games/FarmingSimulator2022"),
            ],
            active_profile="FS25",
        )

    def test_apply_profile_mirrors_paths_to_the_top_level(self) -> None:
        s = self._two_profiles()
        s.apply_profile("FS22")
        assert s.active_profile == "FS22"
        assert s.mod_collection_folder == "/games/FarmingSimulator2022/LS_mods"

    def test_apply_profile_mirrors_per_profile_state(self) -> None:
        s = self._two_profiles()
        s.profiles[1].savegames_read = True
        s.profiles[1].active_modpack = "Winter"
        s.apply_profile("FS22")
        assert s.savegames_read is True
        assert s.active_modpack == "Winter"

    def test_sync_writes_top_level_changes_into_the_active_profile(self) -> None:
        s = self._two_profiles()
        s.active_modpack = "Sommer"
        s.sync_active_profile()
        assert s.active_game_profile.active_modpack == "Sommer"

    def test_sync_leaves_the_other_profile_alone(self) -> None:
        s = self._two_profiles()
        s.active_modpack = "Sommer"
        s.sync_active_profile()
        assert s.profiles[1].active_modpack == ""

    def test_sync_on_a_shallow_copy_does_not_write_through(self) -> None:
        """MainWindow.closeEvent() and SettingsDialog both work on
        copy.copy(settings); saving such a copy must not reach into the
        original's profile list."""
        import copy

        original = self._two_profiles()
        clone = copy.copy(original)
        clone.active_modpack = "Sommer"
        clone.sync_active_profile()
        assert original.active_game_profile.active_modpack == ""

    def test_round_trip_keeps_both_profiles(self) -> None:
        s = self._two_profiles()
        restored = Settings.from_json(s.to_json())
        assert restored.profile_names == ["FS25", "FS22"]
        assert restored.active_profile == "FS25"
