"""Tests for InputDeviceCleanupDialog."""
from pathlib import Path

import pytest

from fsmodmanager.gui.dialogs.input_device_cleanup_dialog import InputDeviceCleanupDialog

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
    "    <devices>\n"
    '        <device id="WHEEL_ID" name="Logitech G29 Driving Force Racing Wheel" category="2"/>\n'
    "    </devices>\n"
    "</inputBinding>\n"
)


@pytest.fixture
def xml_path(tmp_path: Path) -> Path:
    p = tmp_path / "inputBinding.xml"
    p.write_bytes(_SAMPLE_XML.encode("utf-8"))
    return p


class TestInputDeviceCleanupDialog:
    def test_lists_registered_device_by_name(self, xml_path: Path, qtbot) -> None:
        dialog = InputDeviceCleanupDialog(xml_path)
        qtbot.addWidget(dialog)
        assert dialog._list.count() == 1
        assert dialog._list.item(0).text() == "Logitech G29 Driving Force Racing Wheel"

    def test_remove_button_disabled_without_selection(self, xml_path: Path, qtbot) -> None:
        dialog = InputDeviceCleanupDialog(xml_path)
        qtbot.addWidget(dialog)
        assert not dialog._btn_remove.isEnabled()

    def test_remove_button_enabled_after_selection(self, xml_path: Path, qtbot) -> None:
        dialog = InputDeviceCleanupDialog(xml_path)
        qtbot.addWidget(dialog)
        dialog._list.setCurrentRow(0)
        assert dialog._btn_remove.isEnabled()

    def test_confirmed_removal_updates_file(self, xml_path: Path, qtbot, monkeypatch) -> None:
        dialog = InputDeviceCleanupDialog(xml_path)
        qtbot.addWidget(dialog)
        dialog._list.setCurrentRow(0)

        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.input_device_cleanup_dialog.QMessageBox.question",
            lambda *a, **kw: __import__(
                "fsmodmanager.gui.dialogs.input_device_cleanup_dialog",
                fromlist=["QMessageBox"],
            ).QMessageBox.StandardButton.Yes,
        )
        infos = []
        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.input_device_cleanup_dialog.QMessageBox.information",
            lambda *a, **kw: infos.append(a[2]),
        )

        dialog._btn_remove.click()

        assert infos, "Result info dialog was not shown"
        assert "2" in infos[0]
        # No <binding device="WHEEL_ID" .../> left in any actionBinding -
        # but the device's own <devices><device id="WHEEL_ID"> registration
        # is intentionally left untouched.
        text = xml_path.read_text(encoding="utf-8-sig")
        assert 'device="WHEEL_ID"' not in text
        assert 'id="WHEEL_ID"' in text

    def test_declined_confirmation_leaves_file_untouched(
        self, xml_path: Path, qtbot, monkeypatch
    ) -> None:
        original = xml_path.read_bytes()
        dialog = InputDeviceCleanupDialog(xml_path)
        qtbot.addWidget(dialog)
        dialog._list.setCurrentRow(0)

        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.input_device_cleanup_dialog.QMessageBox.question",
            lambda *a, **kw: __import__(
                "fsmodmanager.gui.dialogs.input_device_cleanup_dialog",
                fromlist=["QMessageBox"],
            ).QMessageBox.StandardButton.No,
        )

        dialog._btn_remove.click()

        assert xml_path.read_bytes() == original

    def test_no_devices_shows_placeholder_and_no_crash(self, tmp_path: Path, qtbot) -> None:
        p = tmp_path / "inputBinding.xml"
        p.write_text('<inputBinding><actionBinding action="X"/></inputBinding>', encoding="utf-8")
        dialog = InputDeviceCleanupDialog(p)
        qtbot.addWidget(dialog)
        assert dialog._list.count() == 1
        assert not dialog._btn_remove.isEnabled()

    def test_missing_file_rejects_dialog(self, tmp_path: Path, qtbot, monkeypatch) -> None:
        monkeypatch.setattr(
            "fsmodmanager.gui.dialogs.input_device_cleanup_dialog.QMessageBox.critical",
            lambda *a, **kw: None,
        )
        dialog = InputDeviceCleanupDialog(tmp_path / "does_not_exist.xml")
        qtbot.addWidget(dialog)
        assert dialog.result() == dialog.DialogCode.Rejected
