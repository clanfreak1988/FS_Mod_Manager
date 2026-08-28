from pathlib import Path

import pytest

from fsmodmanager.core.parser.mod_parser import ModParseError, parse_mod


class TestParseModSuccess:
    def test_filename_is_zip_basename(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.filename == "FS25_ModEnDds.zip"

    def test_author_extracted(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.author == "Max Mustermann"

    def test_version_extracted(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.version == "1.2.3.4"

    def test_title_en_preferred(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.title == "English Title"

    def test_icon_filename_dds(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.icon_filename == "icon.dds"

    def test_icon_path_none_after_parse(self, mod_en_dds: Path) -> None:
        """icon_path is set by Phase 3 (DDS converter), not by the parser."""
        mod = parse_mod(mod_en_dds)
        assert mod.icon_path is None

    def test_is_map_false_for_regular_mod(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.is_map is False


class TestMapDetection:
    def test_is_map_true_when_maps_element_present(self, mod_map: Path) -> None:
        mod = parse_mod(mod_map)
        assert mod.is_map is True

    def test_map_mod_other_fields_still_parsed(self, mod_map: Path) -> None:
        mod = parse_mod(mod_map)
        assert mod.title == "Test Map"
        assert mod.author == "Map Author"
        assert mod.version == "1.0.0.0"


class TestTitleFallback:
    def test_de_fallback_when_no_en(self, mod_de_only: Path) -> None:
        mod = parse_mod(mod_de_only)
        assert mod.title == "Nur Deutsch"

    def test_en_wins_over_de(self, mod_en_dds: Path) -> None:
        mod = parse_mod(mod_en_dds)
        assert mod.title == "English Title"


class TestPngIconReference:
    def test_png_icon_filename_stored_as_is(self, mod_png_icon: Path) -> None:
        """Parser stores icon_filename verbatim; DDS vs PNG resolved in Phase 3."""
        mod = parse_mod(mod_png_icon)
        assert mod.icon_filename == "store/icon.png"

    def test_png_mod_fields_correct(self, mod_png_icon: Path) -> None:
        mod = parse_mod(mod_png_icon)
        assert mod.author == "Anna Author"
        assert mod.version == "2.0.0.0"
        assert mod.title == "PNG Icon Mod"


class TestErrorCases:
    def test_missing_moddesc_raises(self, mod_no_moddesc: Path) -> None:
        with pytest.raises(ModParseError, match="modDesc.xml"):
            parse_mod(mod_no_moddesc)

    def test_corrupt_zip_raises(self, mod_corrupt_zip: Path) -> None:
        with pytest.raises(ModParseError, match="corrupt"):
            parse_mod(mod_corrupt_zip)
