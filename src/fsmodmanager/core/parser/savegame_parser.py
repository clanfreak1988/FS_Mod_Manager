import xml.etree.ElementTree as ET
from pathlib import Path

from fsmodmanager.core.model.configuration import Configuration


class SavegameParseError(Exception):
    """Raised when a careerSavegame.xml cannot be read or parsed."""


def parse_savegame(
    xml_path: Path,
    config_name: str | None = None,
) -> Configuration:
    """Parse a careerSavegame.xml and return a Configuration.

    Mirrors Java ModPacks.readModsFromSaveGameXml():
    - Reads every <mod modName="…"> element.
    - Filters out PDLC content (modName starting with 'pdlc_').
    - Constructs filenames as modName + '.zip'.
    - Sorting is handled by Configuration.__post_init__ (case-insensitive).

    Args:
        xml_path:    Path to careerSavegame.xml.
        config_name: Name for the resulting Configuration.
                     Defaults to the savegame folder name (xml_path.parent.name),
                     matching Java's behaviour of using the savegame directory name.

    Raises:
        SavegameParseError: if the file does not exist or contains invalid XML.
    """
    name = config_name if config_name is not None else xml_path.parent.name

    try:
        root = ET.parse(xml_path).getroot()
    except FileNotFoundError as exc:
        raise SavegameParseError(
            f"Savegame-Datei nicht gefunden: {xml_path}"
        ) from exc
    except ET.ParseError as exc:
        raise SavegameParseError(
            f"Ungültiges XML in '{xml_path.name}': {exc}"
        ) from exc

    mod_filenames = [
        mod_name + ".zip"
        for node in root.findall("mod")
        if (mod_name := node.get("modName", ""))
        and not mod_name.startswith("pdlc_")
    ]

    return Configuration(name=name, mod_filenames=mod_filenames)
