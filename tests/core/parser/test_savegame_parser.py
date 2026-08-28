from pathlib import Path

import pytest

from fsmodmanager.core.parser.savegame_parser import SavegameParseError, parse_savegame

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SAVEGAME_XML = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<careerSavegame>
    <settings>
        <savegameName>Mein Hof</savegameName>
    </settings>
    <mod modName="FS22_ModA" title="Mod A" version="1.0.0.0" required="false" fileHash="aaa" />
    <mod modName="FS22_ModB" title="Mod B" version="2.0.0.0" required="true"  fileHash="bbb" />
    <mod modName="FS22_modC" title="Mod C" version="3.0.0.0" required="false" fileHash="ccc" />
    <mod modName="pdlc_Premium" title="DLC"  version="1.0"   required="true"  fileHash="ddd" />
</careerSavegame>"""

_ONLY_PDLC_XML = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<careerSavegame>
    <mod modName="pdlc_Content1" title="DLC1" version="1.0" required="true" fileHash="x" />
    <mod modName="pdlc_Content2" title="DLC2" version="1.0" required="true" fileHash="y" />
</careerSavegame>"""

_EMPTY_XML = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<careerSavegame>
</careerSavegame>"""


def _write_savegame(tmp_path: Path, xml: str, folder: str = "savegame1") -> Path:
    savegame_dir = tmp_path / folder
    savegame_dir.mkdir(parents=True)
    xml_path = savegame_dir / "careerSavegame.xml"
    xml_path.write_text(xml, encoding="utf-8")
    return xml_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseSavegame:
    def test_returns_configuration(self, tmp_path: Path) -> None:
        from fsmodmanager.core.model.configuration import Configuration
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        config = parse_savegame(xml_path)
        assert isinstance(config, Configuration)

    def test_config_name_defaults_to_folder_name(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML, folder="savegame3")
        assert parse_savegame(xml_path).name == "savegame3"

    def test_explicit_config_name(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        assert parse_savegame(xml_path, config_name="Mein Hof").name == "Mein Hof"

    def test_mods_extracted_as_zip_filenames(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        config = parse_savegame(xml_path)
        assert "FS22_ModA.zip" in config.mod_filenames
        assert "FS22_ModB.zip" in config.mod_filenames

    def test_pdlc_mods_filtered_out(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        config = parse_savegame(xml_path)
        assert not any(f.startswith("pdlc_") for f in config.mod_filenames)

    def test_only_pdlc_yields_empty_config(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _ONLY_PDLC_XML)
        assert parse_savegame(xml_path).mod_filenames == []

    def test_empty_savegame_yields_empty_config(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _EMPTY_XML)
        assert parse_savegame(xml_path).mod_filenames == []

    def test_mod_count_excludes_pdlc(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        # XML has 3 normal mods + 1 pdlc → 3 expected
        assert len(parse_savegame(xml_path).mod_filenames) == 3

    def test_mod_filenames_sorted_case_insensitive(self, tmp_path: Path) -> None:
        xml_path = _write_savegame(tmp_path, _SAVEGAME_XML)
        names = parse_savegame(xml_path).mod_filenames
        assert names == sorted(names, key=str.casefold)


class TestErrorCases:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SavegameParseError, match="nicht gefunden"):
            parse_savegame(tmp_path / "savegame1" / "careerSavegame.xml")

    def test_invalid_xml_raises(self, tmp_path: Path) -> None:
        broken = tmp_path / "savegame1"
        broken.mkdir()
        (broken / "careerSavegame.xml").write_text("<not closed", encoding="utf-8")
        with pytest.raises(SavegameParseError, match="Ungültiges XML"):
            parse_savegame(broken / "careerSavegame.xml")

    def test_error_message_contains_filename(self, tmp_path: Path) -> None:
        broken = tmp_path / "mySave"
        broken.mkdir()
        (broken / "careerSavegame.xml").write_text("<<bad>>", encoding="utf-8")
        with pytest.raises(SavegameParseError, match="careerSavegame.xml"):
            parse_savegame(broken / "careerSavegame.xml")
