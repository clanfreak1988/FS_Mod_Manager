"""Tests for MovePromptDialog."""
from datetime import datetime
from pathlib import Path

import pytest

from fsmodmanager.core.service.collection_service import ConflictResolution, MoveConflict
from fsmodmanager.gui.dialogs.move_prompt_dialog import MovePromptDialog


def _conflict(source_version: str = "1.2.0.0", target_version: str = "1.1.0.0") -> MoveConflict:
    return MoveConflict(
        filename="FS22_Test.zip",
        source_path=Path("/src/FS22_Test.zip"),
        source_size=1024,
        source_modified=datetime(2024, 3, 15, 10, 30),
        source_version=source_version,
        target_path=Path("/col/FS22_Test.zip"),
        target_size=2048,
        target_modified=datetime(2024, 1, 5, 8, 0),
        target_version=target_version,
    )


class TestMovePromptDialog:
    def test_default_resolution_is_skip(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        assert dialog.resolution is ConflictResolution.SKIP

    def test_overwrite_button_sets_overwrite(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        dialog._btn_overwrite.click()
        assert dialog.resolution is ConflictResolution.OVERWRITE

    def test_keep_button_sets_keep_existing(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        dialog._btn_keep.click()
        assert dialog.resolution is ConflictResolution.KEEP_EXISTING

    def test_skip_button_sets_skip(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        dialog._btn_skip.click()
        assert dialog.resolution is ConflictResolution.SKIP

    def test_overwrite_accepts_dialog(self, qtbot) -> None:
        from PySide6.QtWidgets import QDialog
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            dialog._btn_overwrite.click()

    def test_keep_accepts_dialog(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            dialog._btn_keep.click()

    def test_skip_accepts_dialog(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.accepted, timeout=1000):
            dialog._btn_skip.click()

    def test_filename_shown_in_dialog(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict())
        qtbot.addWidget(dialog)
        # The headline label contains the filename
        found = False
        for child in dialog.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel):
            if "FS22_Test.zip" in child.text():
                found = True
                break
        assert found, "Filename not found in any label"

    def test_versions_shown_in_dialog(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict(source_version="1.2.0.0", target_version="1.1.0.0"))
        qtbot.addWidget(dialog)
        labels = {
            child.text()
            for child in dialog.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
        }
        assert "1.2.0.0" in labels
        assert "1.1.0.0" in labels

    def test_unknown_version_shown_as_unbekannt(self, qtbot) -> None:
        dialog = MovePromptDialog(_conflict(source_version="", target_version=""))
        qtbot.addWidget(dialog)
        labels = {
            child.text()
            for child in dialog.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
        }
        assert "unbekannt" in labels
