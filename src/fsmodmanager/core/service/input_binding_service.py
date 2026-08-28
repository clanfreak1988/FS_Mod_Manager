"""InputBindingService – reads/edits FS's inputBinding.xml.

New feature, no Java equivalent. FS stores all control bindings in
inputBinding.xml, which lives next to the mods folder
(<gameHome>/inputBinding.xml, i.e. Path(source_mod_folder).parent). Every
<actionBinding> holds one <binding device="..." .../> per assigned key/
button/axis; the referenced device ID is either a symbolic built-in
("KB_MOUSE_DEFAULT", "GAMEPAD_DEFAULT") or a real peripheral's product ID,
which is separately registered with a human-readable name in the
<devices><device id name> section near the end of the file.

FS never cleans these up: once a wheel/joystick/pedal set is replaced or
unplugged, every <actionBinding> that used it keeps a stale <binding>
entry referencing it forever. This service lists the registered devices
(by name) and can strip every <binding> referencing a chosen device from
the whole file in one pass, leaving the device's own <devices><device>
registration (and its axis attributes) untouched – only its action
assignments are cleared.
"""
from __future__ import annotations

import io
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


class InputBindingError(Exception):
    """User-facing error from the input-binding service.

    The message is in plain German and suitable for direct display in the
    GUI – no stacktrace, no internal details.
    """


@dataclass(frozen=True)
class InputDevice:
    """A physical device FS has registered, as listed in <devices>."""
    device_id: str
    name: str


def list_devices(xml_path: Path) -> list[InputDevice]:
    """Return every device FS has registered, in file order.

    Only devices explicitly listed under <devices><device name="..."> are
    returned – these are the ones with a human-readable name. The built-in
    "KB_MOUSE_DEFAULT"/"GAMEPAD_DEFAULT" pseudo-devices have no such entry
    and are intentionally not offered here; bulk-removing keyboard/gamepad
    bindings isn't what this tool is for.

    Raises:
        InputBindingError: if the file is missing or not valid XML.
    """
    root = _parse_tree(xml_path).getroot()
    devices: list[InputDevice] = []
    for device_el in root.findall("./devices/device"):
        device_id = device_el.get("id")
        name = device_el.get("name")
        if device_id and name:
            devices.append(InputDevice(device_id=device_id, name=name))
    return devices


def remove_device_bindings(
    xml_path: Path,
    device_id: str,
    *,
    dry_run: bool = False,
) -> int:
    """Remove every <binding device="device_id" .../> from every
    <actionBinding>, in place.

    The device's own <devices><device> entry is left untouched – only the
    per-action key/button/axis assignments are cleared. An <actionBinding>
    left with no <binding> children becomes an empty/self-closing element,
    same as FS itself writes for unbound actions.

    A one-shot backup of the original file is written to
    "<xml_path.name>.bak" (overwriting any previous backup) before the file
    is modified, so a mistaken removal can be undone by hand.

    Args:
        xml_path: Path to inputBinding.xml.
        device_id: The `id` of an entry from list_devices().
        dry_run: If True, only count matching bindings – nothing is written
            and no backup is made. Used by the GUI to show a count before
            asking for confirmation.

    Returns:
        The number of <binding> elements removed (or that would be, for a
        dry run).

    Raises:
        InputBindingError: if the file is missing, not valid XML, or can't
            be written back.
    """
    tree = _parse_tree(xml_path)
    root = tree.getroot()

    matches: list[tuple[ET.Element, ET.Element]] = [
        (action_binding, binding)
        for action_binding in root.findall("./actionBinding")
        for binding in action_binding.findall("binding")
        if binding.get("device") == device_id
    ]

    if not matches or dry_run:
        return len(matches)

    for action_binding, binding in matches:
        action_binding.remove(binding)

    _backup(xml_path)
    _write(tree, xml_path)
    return len(matches)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _parse_tree(xml_path: Path) -> ET.ElementTree:
    if not xml_path.is_file():
        raise InputBindingError(f"Datei nicht gefunden: {xml_path}")
    try:
        return ET.parse(xml_path)
    except ET.ParseError as exc:
        raise InputBindingError(
            f"'{xml_path.name}' ist keine gültige XML-Datei: {exc}"
        ) from exc


def _backup(xml_path: Path) -> None:
    backup_path = xml_path.with_name(xml_path.name + ".bak")
    try:
        shutil.copy2(xml_path, backup_path)
    except OSError as exc:
        raise InputBindingError(
            f"Konnte keine Sicherung von '{xml_path.name}' anlegen: "
            f"{exc.strerror or exc}"
        ) from exc


def _write(tree: ET.ElementTree, xml_path: Path) -> None:
    ET.indent(tree, space="    ")
    try:
        # ElementTree.write(..., encoding="utf-8-sig") would write that literal
        # (non-standard, potentially parser-confusing) string into the XML
        # declaration itself - it does NOT special-case it to "utf-8" the way
        # e.g. open(encoding=...) does. So: serialize with a correct "utf-8"
        # declaration into memory, then prepend the BOM byte-for-byte, matching
        # how FS itself writes this file (BOM present, declaration says
        # plain "utf-8").
        buffer = io.BytesIO()
        tree.write(buffer, encoding="utf-8", xml_declaration=True)
        xml_path.write_bytes(b"\xef\xbb\xbf" + buffer.getvalue())
    except OSError as exc:
        raise InputBindingError(
            f"Konnte '{xml_path}' nicht speichern: {exc.strerror or exc}"
        ) from exc
