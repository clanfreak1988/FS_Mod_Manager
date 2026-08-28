import json

import pytest

from fsmodmanager.core.model.configuration import Configuration


@pytest.fixture
def sample_config() -> Configuration:
    return Configuration(
        name="Mein Hof",
        mod_filenames=["FS25_ZMod.zip", "FS25_AMod.zip", "FS25_MMod.zip"],
    )


class TestConfigurationSerialization:
    def test_to_dict_contains_all_fields(self, sample_config: Configuration) -> None:
        d = sample_config.to_dict()
        assert d["name"] == "Mein Hof"
        assert "mod_filenames" in d

    def test_roundtrip_json(self, sample_config: Configuration) -> None:
        restored = Configuration.from_json(sample_config.to_json())
        assert restored == sample_config

    def test_from_dict_roundtrip(self, sample_config: Configuration) -> None:
        restored = Configuration.from_dict(sample_config.to_dict())
        assert restored == sample_config

    def test_to_json_is_valid_json(self, sample_config: Configuration) -> None:
        parsed = json.loads(sample_config.to_json())
        assert isinstance(parsed, dict)

    def test_mod_filenames_sorted_case_insensitive(self) -> None:
        config = Configuration(
            name="Test",
            mod_filenames=["FS25_ZMod.zip", "FS25_aMod.zip", "FS25_MMod.zip"],
        )
        assert config.mod_filenames == sorted(
            ["FS25_ZMod.zip", "FS25_aMod.zip", "FS25_MMod.zip"], key=str.casefold
        )

    def test_empty_mod_filenames(self) -> None:
        config = Configuration(name="Leer")
        assert config.mod_filenames == []

    def test_from_dict_missing_mod_filenames_defaults_to_empty(self) -> None:
        config = Configuration.from_dict({"name": "Test"})
        assert config.mod_filenames == []
