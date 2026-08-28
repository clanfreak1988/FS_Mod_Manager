import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from fsmodmanager.core.service.input_binding_service import (
    InputBindingError,
    InputDevice,
    list_devices,
    remove_device_bindings,
)

_SAMPLE_XML = (
    "﻿"
    '<?xml version="1.0" encoding="utf-8" standalone="no" ?>\n'
    '<inputBinding version="24" bindingVersion="1">\n'
    '    <actionBinding action="JUMP">\n'
    '        <binding device="KB_MOUSE_DEFAULT" input="KEY_space" axisComponent="+" neutralInput="0" index="1"/>\n'
    '        <binding device="WHEEL_ID" input="BUTTON_2" axisComponent="+" neutralInput="0" index="1"/>\n'
    "    </actionBinding>\n"
    '    <actionBinding action="BRAKE">\n'
    '        <binding device="WHEEL_ID" input="AXIS_3" axisComponent="+" neutralInput="0" index="1"/>\n'
    "    </actionBinding>\n"
    '    <actionBinding action="HANDBRAKE">\n'
    '        <binding device="GAMEPAD_DEFAULT" input="BUTTON_1" axisComponent="+" neutralInput="0" index="1"/>\n'
    "    </actionBinding>\n"
    '    <actionBinding action="UNBOUND_ACTION"/>\n'
    "    <devices>\n"
    '        <device id="WHEEL_ID" name="Logitech G29 Driving Force Racing Wheel" category="2">\n'
    '            <attributes axis="0" deadzone="0.140000" sensitivity="1.000000"/>\n'
    "        </device>\n"
    '        <device id="OTHER_ID" name="Thrustmaster HOTAS Warthog" category="1"/>\n'
    "    </devices>\n"
    "</inputBinding>\n"
)


@pytest.fixture
def xml_path(tmp_path: Path) -> Path:
    p = tmp_path / "inputBinding.xml"
    p.write_bytes(_SAMPLE_XML.encode("utf-8"))
    return p


class TestListDevices:
    def test_returns_registered_devices_in_order(self, xml_path: Path) -> None:
        devices = list_devices(xml_path)
        assert devices == [
            InputDevice(device_id="WHEEL_ID", name="Logitech G29 Driving Force Racing Wheel"),
            InputDevice(device_id="OTHER_ID", name="Thrustmaster HOTAS Warthog"),
        ]

    def test_symbolic_builtin_devices_not_included(self, xml_path: Path) -> None:
        names = {d.name for d in list_devices(xml_path)}
        assert "KB_MOUSE_DEFAULT" not in names
        assert "GAMEPAD_DEFAULT" not in names
        ids = {d.device_id for d in list_devices(xml_path)}
        assert "KB_MOUSE_DEFAULT" not in ids
        assert "GAMEPAD_DEFAULT" not in ids

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(InputBindingError):
            list_devices(tmp_path / "does_not_exist.xml")

    def test_invalid_xml_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "broken.xml"
        p.write_text("<inputBinding><notclosed>", encoding="utf-8")
        with pytest.raises(InputBindingError):
            list_devices(p)

    def test_no_devices_section_returns_empty_list(self, tmp_path: Path) -> None:
        p = tmp_path / "no_devices.xml"
        p.write_text('<inputBinding><actionBinding action="X"/></inputBinding>', encoding="utf-8")
        assert list_devices(p) == []


class TestRemoveDeviceBindings:
    def test_removes_all_matching_bindings(self, xml_path: Path) -> None:
        removed = remove_device_bindings(xml_path, "WHEEL_ID")
        assert removed == 2

        root = ET.parse(xml_path).getroot()
        remaining_device_attrs = [
            b.get("device")
            for ab in root.findall("./actionBinding")
            for b in ab.findall("binding")
        ]
        assert "WHEEL_ID" not in remaining_device_attrs
        # Untouched bindings for other devices survive.
        assert "KB_MOUSE_DEFAULT" in remaining_device_attrs
        assert "GAMEPAD_DEFAULT" in remaining_device_attrs

    def test_device_registration_itself_is_untouched(self, xml_path: Path) -> None:
        remove_device_bindings(xml_path, "WHEEL_ID")
        devices = list_devices(xml_path)
        assert any(d.device_id == "WHEEL_ID" for d in devices)

    def test_emptied_action_binding_has_no_children(self, xml_path: Path) -> None:
        """BRAKE only had a WHEEL_ID binding - after removal it must become
        an empty element, same shape as FS's own UNBOUND_ACTION."""
        remove_device_bindings(xml_path, "WHEEL_ID")
        root = ET.parse(xml_path).getroot()
        brake = next(ab for ab in root.findall("./actionBinding") if ab.get("action") == "BRAKE")
        assert list(brake) == []

    def test_dry_run_does_not_modify_file(self, xml_path: Path) -> None:
        original_bytes = xml_path.read_bytes()
        count = remove_device_bindings(xml_path, "WHEEL_ID", dry_run=True)
        assert count == 2
        assert xml_path.read_bytes() == original_bytes
        assert not xml_path.with_name(xml_path.name + ".bak").exists()

    def test_no_matches_returns_zero_and_does_not_touch_file(self, xml_path: Path) -> None:
        original_bytes = xml_path.read_bytes()
        count = remove_device_bindings(xml_path, "NONEXISTENT_ID")
        assert count == 0
        assert xml_path.read_bytes() == original_bytes
        assert not xml_path.with_name(xml_path.name + ".bak").exists()

    def test_creates_backup_before_writing(self, xml_path: Path) -> None:
        original_bytes = xml_path.read_bytes()
        remove_device_bindings(xml_path, "WHEEL_ID")
        backup_path = xml_path.with_name(xml_path.name + ".bak")
        assert backup_path.exists()
        assert backup_path.read_bytes() == original_bytes

    def test_output_is_well_formed_xml(self, xml_path: Path) -> None:
        remove_device_bindings(xml_path, "WHEEL_ID")
        ET.parse(xml_path)  # raises on malformed XML

    def test_output_keeps_utf8_bom(self, xml_path: Path) -> None:
        remove_device_bindings(xml_path, "WHEEL_ID")
        assert xml_path.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_output_declares_plain_utf8_not_utf8_sig(self, xml_path: Path) -> None:
        """encoding='utf-8-sig' is not a standard XML encoding name and must
        never leak into the declaration text itself - only the BOM bytes
        should carry that information."""
        remove_device_bindings(xml_path, "WHEEL_ID")
        text = xml_path.read_bytes().decode("utf-8-sig")
        assert "utf-8-sig" not in text.lower()
        assert "encoding='utf-8'" in text.lower() or 'encoding="utf-8"' in text.lower()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(InputBindingError):
            remove_device_bindings(tmp_path / "does_not_exist.xml", "WHEEL_ID")
