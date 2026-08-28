"""Session-scoped fixture ZIPs written to tests/core/fixtures/.

Each fixture represents a different real-world mod structure.
The files are created once per test session and reused.
"""
import zipfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _write_zip(name: str, moddesc_xml: str, extra_entries: dict[str, bytes] | None = None) -> Path:
    FIXTURES_DIR.mkdir(exist_ok=True)
    path = FIXTURES_DIR / name
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modDesc.xml", moddesc_xml.encode("utf-8"))
        for entry_name, data in (extra_entries or {}).items():
            zf.writestr(entry_name, data)
    return path


# ---------------------------------------------------------------------------
# Fixture 1 – normal mod, <en> title, .dds icon
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_en_dds(tmp_path_factory) -> Path:
    xml = """\
<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<modDesc descVersion="72">
    <author>Max Mustermann</author>
    <version>1.2.3.4</version>
    <title>
        <en>English Title</en>
        <de>Deutscher Titel</de>
    </title>
    <iconFilename>icon.dds</iconFilename>
</modDesc>"""
    return _write_zip("FS22_ModEnDds.zip", xml, {"icon.dds": b"\x00" * 16})


# ---------------------------------------------------------------------------
# Fixture 2 – mod with .png reference in modDesc (no .dds in zip)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_png_icon(tmp_path_factory) -> Path:
    xml = """\
<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<modDesc descVersion="68">
    <author>Anna Author</author>
    <version>2.0.0.0</version>
    <title>
        <en>PNG Icon Mod</en>
    </title>
    <iconFilename>store/icon.png</iconFilename>
</modDesc>"""
    return _write_zip("FS22_ModPngIcon.zip", xml, {"store/icon.png": b"\x89PNG\r\n"})


# ---------------------------------------------------------------------------
# Fixture 3 – no <en>, only <de> title
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_de_only(tmp_path_factory) -> Path:
    xml = """\
<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<modDesc descVersion="72">
    <author>Klaus Kowalski</author>
    <version>3.1.0.0</version>
    <title>
        <de>Nur Deutsch</de>
    </title>
    <iconFilename>icon.dds</iconFilename>
</modDesc>"""
    return _write_zip("FS22_ModDeOnly.zip", xml)


# ---------------------------------------------------------------------------
# Fixture 3b – map mod (<maps> element present), based on a real-world map
# mod's modDesc.xml structure (FS25_HofBergmann.zip)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_map(tmp_path_factory) -> Path:
    xml = """\
<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<modDesc descVersion="83">
    <author>Map Author</author>
    <version>1.0.0.0</version>
    <title>
        <en>Test Map</en>
    </title>
    <iconFilename>icon.dds</iconFilename>
    <maps>
        <map id="TestMap" className="Mission00" filename="$dataS/scripts/mission00.lua" configFilename="testMap.xml">
            <title>
                <en>TEST MAP</en>
            </title>
        </map>
    </maps>
</modDesc>"""
    return _write_zip("FS22_ModMap.zip", xml, {"icon.dds": b"\x00" * 16})


# ---------------------------------------------------------------------------
# Fixture 4 – missing modDesc.xml (error case)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_no_moddesc(tmp_path_factory) -> Path:
    FIXTURES_DIR.mkdir(exist_ok=True)
    path = FIXTURES_DIR / "FS22_NoModDesc.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", b"no moddesc here")
    return path


# ---------------------------------------------------------------------------
# Fixture 5 – corrupt / not a ZIP at all (error case)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mod_corrupt_zip(tmp_path_factory) -> Path:
    FIXTURES_DIR.mkdir(exist_ok=True)
    path = FIXTURES_DIR / "FS22_Corrupt.zip"
    path.write_bytes(b"this is not a zip file at all")
    return path
