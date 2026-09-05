import json

import pytest

from fsmodmanager.core.model.settings import Settings


@pytest.fixture
def sample_settings() -> Settings:
    return Settings(
        source_mod_folder="/home/user/Documents/My Games/FarmingSimulator2025/mods",
        mod_collection_folder="/home/user/Documents/My Games/FarmingSimulator2025/LS_mods",
        savegame_path="/home/user/Documents/My Games/FarmingSimulator2025",
    )


class TestSettingsSerialization:
    def test_to_dict_contains_all_fields(self, sample_settings: Settings) -> None:
        d = sample_settings.to_dict()
        assert set(d.keys()) == {
            "source_mod_folder",
            "mod_collection_folder",
            "savegame_path",
            "savegames_read",
            "active_modpack",
            "visible_icon_column",
            "scene_width",
            "scene_height",
            "theme",
            "profiles",
            "active_profile",
        }

    def test_roundtrip_json(self, sample_settings: Settings) -> None:
        restored = Settings.from_json(sample_settings.to_json())
        assert restored == sample_settings

    def test_from_dict_roundtrip(self, sample_settings: Settings) -> None:
        restored = Settings.from_dict(sample_settings.to_dict())
        assert restored == sample_settings

    def test_to_json_is_valid_json(self, sample_settings: Settings) -> None:
        parsed = json.loads(sample_settings.to_json())
        assert isinstance(parsed, dict)

    def test_defaults(self, sample_settings: Settings) -> None:
        assert sample_settings.savegames_read is False
        assert sample_settings.active_modpack == ""
        assert sample_settings.visible_icon_column is True
        assert sample_settings.scene_width == 1150.0
        assert sample_settings.scene_height == 700.0
        assert sample_settings.theme == "system"

    def test_from_dict_optional_fields_use_defaults(self) -> None:
        minimal = {
            "source_mod_folder": "/mods",
            "mod_collection_folder": "/collection",
            "savegame_path": "/savegames",
        }
        settings = Settings.from_dict(minimal)
        assert settings.savegames_read is False
        assert settings.active_modpack == ""
        assert settings.visible_icon_column is True
        assert settings.scene_width == 1150.0
        assert settings.scene_height == 700.0
        assert settings.theme == "system"

    def test_theme_roundtrip(self) -> None:
        s = Settings(
            source_mod_folder="/mods",
            mod_collection_folder="/collection",
            savegame_path="/saves",
            theme="dark",
        )
        assert Settings.from_json(s.to_json()).theme == "dark"

    def test_active_modpack_roundtrip(self) -> None:
        s = Settings(
            source_mod_folder="/mods",
            mod_collection_folder="/collection",
            savegame_path="/saves",
            active_modpack="Mein Hof",
        )
        assert Settings.from_json(s.to_json()).active_modpack == "Mein Hof"
