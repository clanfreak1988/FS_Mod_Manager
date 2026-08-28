"""Integration tests against real mod ZIPs.

Place actual FS mod ZIPs in tests/integration/fixtures/ to activate these tests.
That directory is gitignored (copyright + file size).

Run only integration tests:
    pytest -m integration

Run everything except integration tests (default CI):
    pytest -m "not integration"
"""
import zipfile
from pathlib import Path

import pytest

from fsmodmanager.core.parser.dds_converter import convert_icon
from fsmodmanager.core.parser.mod_parser import ModParseError, parse_mod

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_has_mods = any(FIXTURES_DIR.glob("*.zip"))


@pytest.mark.integration
@pytest.mark.skipif(not _has_mods, reason="Keine Mod-ZIPs in tests/integration/fixtures/")
class TestRealMods:
    def test_all_mods_parseable(self) -> None:
        """Every ZIP in the fixtures dir must parse without raising ModParseError."""
        failed = []
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                parse_mod(zip_path)
            except ModParseError as exc:
                failed.append(f"{zip_path.name}: {exc}")
        assert not failed, "Parse-Fehler bei echten Mods:\n" + "\n".join(failed)

    def test_all_mods_have_non_empty_title(self) -> None:
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
                assert mod.title, f"{zip_path.name}: leerer Titel"
            except ModParseError:
                pass  # bereits von test_all_mods_parseable abgedeckt

    def test_all_mods_have_non_empty_author(self) -> None:
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
                assert mod.author, f"{zip_path.name}: leerer Autor"
            except ModParseError:
                pass

    def test_all_mods_have_non_empty_version(self) -> None:
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
                assert mod.version, f"{zip_path.name}: leere Version"
            except ModParseError:
                pass

    def test_all_mods_have_icon_filename(self) -> None:
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
                assert mod.icon_filename, f"{zip_path.name}: kein icon_filename"
            except ModParseError:
                pass

    def test_filenames_match_zip_basename(self) -> None:
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
                assert mod.filename == zip_path.name
            except ModParseError:
                pass

    def test_icons_convertible(self) -> None:
        """Icons aus echten Mods müssen von Pillow (oder wand) gelesen werden können."""
        failed = []
        for zip_path in sorted(FIXTURES_DIR.glob("*.zip")):
            try:
                mod = parse_mod(zip_path)
            except ModParseError:
                continue

            icon_fn = mod.icon_filename
            # Java-Verhalten: wenn .png im Pfad steht, erst .dds versuchen
            dds_fn = icon_fn.replace(".png", ".dds") if ".png" in icon_fn else icon_fn

            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                actual_fn = dds_fn if dds_fn in names else icon_fn
                if actual_fn not in names:
                    failed.append(f"{zip_path.name}: Icon '{icon_fn}' nicht im ZIP")
                    continue
                data = zf.read(actual_fn)

            if convert_icon(data, actual_fn) is None:
                failed.append(f"{zip_path.name}: Icon '{actual_fn}' konnte nicht gelesen werden (None)")

        assert not failed, "Icon-Konvertierungsfehler:\n" + "\n".join(failed)
