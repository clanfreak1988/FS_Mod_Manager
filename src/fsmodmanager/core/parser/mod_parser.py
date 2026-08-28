import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from fsmodmanager.core.model.mod import Mod


class ModParseError(Exception):
    """Raised when a mod ZIP cannot be parsed (missing modDesc.xml, corrupt ZIP, …)."""


def parse_mod(zip_path: Path) -> Mod:
    """Parse a mod ZIP and return a Mod instance.

    Mirrors Java Main.readModZip / createMod logic:
    - Opens zip_path as a ZIP archive.
    - Reads modDesc.xml for author, title (en → de fallback), version, iconFilename.
    - icon_path is left None; DDS→PNG conversion is done in Phase 3.
    - is_map (new, no Java equivalent) is True iff modDesc.xml has a <maps>
      element, the marker FS itself uses for map mods.

    Raises:
        ModParseError: if the ZIP is corrupt or modDesc.xml is missing/unreadable.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if "modDesc.xml" not in names:
                raise ModParseError(f"{zip_path.name}: no modDesc.xml found in ZIP")
            with zf.open("modDesc.xml") as f:
                try:
                    root = ET.parse(f).getroot()
                except ET.ParseError as exc:
                    raise ModParseError(
                        f"{zip_path.name}: modDesc.xml is not valid XML"
                    ) from exc

    except zipfile.BadZipFile as exc:
        raise ModParseError(f"{zip_path.name}: corrupt or invalid ZIP") from exc

    author = _text(root, "author")
    version = _text(root, "version")
    icon_filename = _text(root, "iconFilename")
    title = _parse_title(root.find("title"))
    is_map = root.find("maps") is not None

    return Mod(
        filename=zip_path.name,
        title=title,
        author=author,
        version=version,
        icon_filename=icon_filename,
        is_map=is_map,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(root: ET.Element, tag: str) -> str:
    """Return stripped text of a direct child element, or empty string."""
    el = root.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _parse_title(title_el: ET.Element | None) -> str:
    """Return the best available title string.

    Priority: <en> → <de> → any other language child → element text.
    Matches Java's regex order (en first, de fallback).
    """
    if title_el is None:
        return ""
    for lang in ("en", "de"):
        child = title_el.find(lang)
        if child is not None and child.text:
            return child.text.strip()
    # Fallback: first child with text
    for child in title_el:
        if child.text:
            return child.text.strip()
    return (title_el.text or "").strip()
