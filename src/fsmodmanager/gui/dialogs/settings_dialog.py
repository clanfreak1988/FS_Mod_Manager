"""SettingsDialog – edit all application settings in one form.

Opens pre-filled with the current Settings, returns a modified copy on OK.

First-run mode (first_run=True)
--------------------------------
  • Title is set to "Einstellungen – Erststart"
  • The OK button is labelled "Weiter" and stays disabled until all three
    path fields point to directories that actually exist on disk.
  • The Cancel button is hidden; closing the window without confirming
    exits the application (matching the Java ``firstStart()`` behaviour).
  • Each path label is coloured green (exists) or red (missing).

Normal mode (first_run=False, the default)
-------------------------------------------
  • OK / Cancel buttons behave normally.
  • Path-existence colouring and OK-button gating are still applied so
    the user gets clear feedback, but Cancel is always available.

Usage
-----
    dialog = SettingsDialog(current_settings, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        vm.save_settings(dialog.settings)
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from fsmodmanager.core.model.settings import Settings
from fsmodmanager.gui.theme import THEME_DARK, THEME_LIGHT, THEME_SYSTEM, apply_theme

_THEME_ITEMS = [
    ("System", THEME_SYSTEM),
    ("Hell", THEME_LIGHT),
    ("Dunkel", THEME_DARK),
]

_GREEN = "color: green; font-weight: bold;"
_RED   = "color: red;  font-weight: bold;"


class SettingsDialog(QDialog):
    """Modal settings editor.

    Parameters
    ----------
    current : Settings
        The settings object used to pre-fill the form.
    first_run : bool
        When *True* the dialog operates in first-run / guided mode:
        Cancel is hidden, the OK button is labelled "Weiter" and disabled
        until all paths exist, and closing the window exits the application.
    parent :
        Qt parent widget.

    Attributes
    ----------
    settings : Settings
        The modified settings object, available after the dialog is accepted.
        Contains the original values unchanged if the dialog is rejected.
    """

    def __init__(self, current: Settings, *, first_run: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._original = current
        self._first_run = first_run
        self.settings: Settings = copy.copy(current)
        self.setWindowTitle("Einstellungen – Erststart" if first_run else "Einstellungen")
        self.setMinimumWidth(540)
        self.setModal(True)
        self._build_ui()
        self._populate(current)
        self._refresh_validation()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        if self._first_run:
            hint = QLabel(
                "Es müssen die Pfade angegeben werden.\n"
                "So lange die Pfade nicht existieren, wird der Weiter-Button "
                "nicht aktiv geschaltet!"
            )
            hint.setWordWrap(True)
            root.addWidget(hint)

        root.addWidget(self._build_paths_group())
        root.addWidget(self._build_display_group())
        root.addWidget(self._build_button_box())

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Pfade")
        form = QFormLayout(group)
        form.setSpacing(8)

        self._edit_source     = QLineEdit()
        self._edit_collection = QLineEdit()
        self._edit_savegame   = QLineEdit()

        self._lbl_source     = QLabel("FS Mod-Ordner:")
        self._lbl_collection = QLabel("Sammelordner:")
        self._lbl_savegame   = QLabel("Savegame-Pfad:")

        # Connect text changes to validation
        self._edit_source.textChanged.connect(self._refresh_validation)
        self._edit_collection.textChanged.connect(self._refresh_validation)
        self._edit_savegame.textChanged.connect(self._refresh_validation)

        form.addRow(self._lbl_source,     self._path_row(self._edit_source,     self._browse_source))
        form.addRow(self._lbl_collection, self._path_row(self._edit_collection, self._browse_collection))
        form.addRow(self._lbl_savegame,   self._path_row(self._edit_savegame,   self._browse_savegame))

        return group

    def _build_display_group(self) -> QGroupBox:
        group = QGroupBox("Ansicht")
        form = QFormLayout(group)
        form.setSpacing(8)
        self._chk_icon_column = QCheckBox("Icon-Spalte anzeigen")
        form.addRow(self._chk_icon_column)

        self._combo_theme = QComboBox()
        for label, _value in _THEME_ITEMS:
            self._combo_theme.addItem(label)
        self._combo_theme.setToolTip(
            "\"System\" übernimmt automatisch die Hell-/Dunkel-Einstellung "
            "des Betriebssystems."
        )
        self._combo_theme.currentIndexChanged.connect(self._on_theme_preview)
        form.addRow(QLabel("Design:"), self._combo_theme)

        return group

    def _build_button_box(self) -> QDialogButtonBox:
        if self._first_run:
            box = QDialogButtonBox()
            self._ok_btn = box.addButton("Weiter", QDialogButtonBox.ButtonRole.AcceptRole)
        else:
            box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            self._ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
            self._ok_btn.setText("Speichern")
            box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
            box.rejected.connect(self.reject)

        box.accepted.connect(self._on_accept)
        self._btn_box = box
        return box

    @staticmethod
    def _path_row(edit: QLineEdit, browse_slot) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(edit, stretch=1)
        btn = QPushButton("…")
        btn.setFixedWidth(30)
        btn.setToolTip("Ordner wählen")
        btn.clicked.connect(browse_slot)
        row.addWidget(btn)
        return row

    # ── validation ────────────────────────────────────────────────────────────

    def _refresh_validation(self) -> None:
        """Colour labels and gate the OK button based on path existence."""
        def _check(edit: QLineEdit, label: QLabel) -> bool:
            p = Path(edit.text().strip())
            exists = p.is_dir()
            label.setStyleSheet(_GREEN if exists else _RED)
            return exists

        ok_source     = _check(self._edit_source,     self._lbl_source)
        ok_collection = _check(self._edit_collection, self._lbl_collection)
        ok_savegame   = _check(self._edit_savegame,   self._lbl_savegame)

        self._ok_btn.setEnabled(ok_source and ok_collection and ok_savegame)

    # ── populate / extract ────────────────────────────────────────────────────

    def _populate(self, s: Settings) -> None:
        self._edit_source.setText(s.source_mod_folder)
        self._edit_collection.setText(s.mod_collection_folder)
        self._edit_savegame.setText(s.savegame_path)
        self._chk_icon_column.setChecked(s.visible_icon_column)
        theme_values = [value for _label, value in _THEME_ITEMS]
        index = theme_values.index(s.theme) if s.theme in theme_values else 0
        self._combo_theme.setCurrentIndex(index)

    def _read_form(self) -> Settings:
        s = copy.copy(self._original)
        s.source_mod_folder    = self._edit_source.text().strip()
        s.mod_collection_folder = self._edit_collection.text().strip()
        s.savegame_path        = self._edit_savegame.text().strip()
        s.visible_icon_column  = self._chk_icon_column.isChecked()
        s.theme                = _THEME_ITEMS[self._combo_theme.currentIndex()][1]
        return s

    # ── browse slots ──────────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        self._pick_dir(self._edit_source, "FS Mod-Ordner wählen")

    def _browse_collection(self) -> None:
        self._pick_dir(self._edit_collection, "Sammelordner wählen")

    def _browse_savegame(self) -> None:
        self._pick_dir(self._edit_savegame, "Savegame-Pfad wählen")

    def _pick_dir(self, edit: QLineEdit, title: str) -> None:
        start = edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, title, start)
        if path:
            edit.setText(path)

    # ── close / reject handling ───────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """On first-run the window cannot be dismissed without completing setup."""
        if self._first_run:
            # Mirror Java: closing the config stage deletes config + exits
            event.accept()
            sys.exit(0)
        super().closeEvent(event)

    # ── theme preview / accept / reject ─────────────────────────────────────────

    def _on_theme_preview(self, _index: int) -> None:
        """Apply the selected theme immediately, so the user sees the effect
        before committing. Reverted in reject() if they cancel instead."""
        apply_theme(_THEME_ITEMS[self._combo_theme.currentIndex()][1])

    def _on_accept(self) -> None:
        self.settings = self._read_form()
        self.accept()

    def reject(self) -> None:
        """Cancel button, X, or Escape: undo the live theme preview, keep the
        original. Overriding reject() itself (rather than only reacting to the
        button box's ``rejected`` signal) ensures every path to cancelling –
        including the window's close button, which Qt's default closeEvent
        routes straight through QDialog.reject() – gets the same cleanup."""
        apply_theme(self._original.theme)
        super().reject()
