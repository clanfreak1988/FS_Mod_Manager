import json
from pathlib import Path

import pytest

from fsmodmanager.core.model.mod import Mod, is_valid_mod_name, sanitize_mod_name


@pytest.fixture
def sample_mod() -> Mod:
    return Mod(
        filename="FS25_SomeMod.zip",
        title="Some Mod",
        author="Max Mustermann",
        version="1.0.0.0",
        icon_filename="icon.dds",
    )


class TestModSerialization:
    def test_to_dict_contains_all_fields(self, sample_mod: Mod) -> None:
        d = sample_mod.to_dict()
        assert d == {
            "filename": "FS25_SomeMod.zip",
            "title": "Some Mod",
            "author": "Max Mustermann",
            "version": "1.0.0.0",
            "icon_filename": "icon.dds",
            "is_map": False,
        }

    def test_to_dict_excludes_icon_path(self, sample_mod: Mod) -> None:
        sample_mod.icon_path = Path("/tmp/icon.png")
        assert "icon_path" not in sample_mod.to_dict()

    def test_roundtrip_json(self, sample_mod: Mod) -> None:
        restored = Mod.from_json(sample_mod.to_json())
        assert restored == sample_mod

    def test_from_dict_roundtrip(self, sample_mod: Mod) -> None:
        restored = Mod.from_dict(sample_mod.to_dict())
        assert restored == sample_mod

    def test_to_json_is_valid_json(self, sample_mod: Mod) -> None:
        parsed = json.loads(sample_mod.to_json())
        assert isinstance(parsed, dict)

    def test_icon_path_not_included_in_equality(self) -> None:
        mod_a = Mod("a.zip", "Title", "Author", "1.0", "icon.dds", icon_path=None)
        mod_b = Mod("a.zip", "Title", "Author", "1.0", "icon.dds", icon_path=Path("/tmp/x.png"))
        assert mod_a == mod_b

    def test_is_map_defaults_to_false(self) -> None:
        mod = Mod("a.zip", "Title", "Author", "1.0", "icon.dds")
        assert mod.is_map is False

    def test_is_map_roundtrip(self) -> None:
        mod = Mod("a.zip", "Title", "Author", "1.0", "icon.dds", is_map=True)
        assert Mod.from_json(mod.to_json()).is_map is True

    def test_is_map_missing_in_dict_defaults_to_false(self) -> None:
        minimal = {
            "filename": "a.zip",
            "title": "Title",
            "author": "Author",
            "version": "1.0",
            "icon_filename": "icon.dds",
        }
        assert Mod.from_dict(minimal).is_map is False


class TestValidModName:
    @pytest.mark.parametrize("filename", [
        "FS25_AdvancedDamageSystem.zip",
        "FS25_Mod_123.zip",
        "_startsWithUnderscore.zip",
        "a.zip",
    ])
    def test_valid_names(self, filename: str) -> None:
        assert is_valid_mod_name(filename) is True

    @pytest.mark.parametrize("filename", [
        "FS25_AdvancedDamageSystem (1).zip",   # space + parentheses (duplicate download)
        "1FS25_StartsWithDigit.zip",           # first char is a digit
        "FS25-Dashes-Not-Allowed.zip",
        "FS25 With Spaces.zip",
        "FS25_Ümlaut.zip",
    ])
    def test_invalid_names(self, filename: str) -> None:
        assert is_valid_mod_name(filename) is False

    def test_extension_is_ignored(self) -> None:
        assert is_valid_mod_name("FS25_Valid.zip") == is_valid_mod_name("FS25_Valid.dat")

    def test_has_invalid_name_property(self) -> None:
        valid = Mod("FS25_Valid.zip", "Title", "Author", "1.0", "icon.dds")
        invalid = Mod("FS25_Invalid (1).zip", "Title", "Author", "1.0", "icon.dds")
        assert valid.has_invalid_name is False
        assert invalid.has_invalid_name is True


class TestSanitizeModName:
    def test_strips_duplicate_download_suffix(self) -> None:
        assert sanitize_mod_name("FS25_AdvancedDamageSystem (1).zip") == "FS25_AdvancedDamageSystem.zip"

    def test_strips_spaces_and_dashes(self) -> None:
        assert sanitize_mod_name("FS25 With-Spaces.zip") == "FS25WithSpaces.zip"

    def test_prefixes_underscore_when_first_char_is_digit(self) -> None:
        assert sanitize_mod_name("1FS25_StartsWithDigit.zip") == "_1FS25_StartsWithDigit.zip"

    def test_valid_name_is_unchanged(self) -> None:
        assert sanitize_mod_name("FS25_AlreadyValid.zip") == "FS25_AlreadyValid.zip"

    def test_result_is_always_valid(self) -> None:
        for filename in [
            "FS25_AdvancedDamageSystem (1).zip",
            "1FS25_StartsWithDigit.zip",
            "FS25-Dashes-Not-Allowed.zip",
            "FS25 With Spaces.zip",
            "() ().zip",
        ]:
            assert is_valid_mod_name(sanitize_mod_name(filename))

    def test_falls_back_to_mod_when_nothing_left(self) -> None:
        assert sanitize_mod_name("() ().zip") == "Mod.zip"

    def test_preserves_extension(self) -> None:
        assert sanitize_mod_name("Bad Name.dat") == "BadName.dat"
