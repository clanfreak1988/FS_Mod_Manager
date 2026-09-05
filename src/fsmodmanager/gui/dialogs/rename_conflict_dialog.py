"""RenameConflictDialog – shown when fixing a mod's invalid filename would
collide with an existing file already sitting under the corrected name in
the collection folder.

Offers the same "Neue übernehmen"/"Vorhandene behalten"/"Überspringen" choice
as MovePromptDialog (same ConflictResolution enum), but with its own wording:
MovePromptDialog's copy specifically describes a collect()-time collision
between the collection folder and the FS mods folder, which doesn't fit a
same-folder rename.

Usage
-----
    dialog = RenameConflictDialog(conflict, new_filename, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        resolution = dialog.resolution
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from fsmodmanager.core.service.collection_service import ConflictResolution, MoveConflict
from fsmodmanager.gui.dialogs.conflict_table import build_conflict_table


class RenameConflictDialog(QDialog):
    """Modal dialog for a filename collision while fixing an invalid mod name.

    `conflict` is a MoveConflict from MainViewModel.check_rename_conflict(),
    built with the invalid-named file as its "source" and the file already
    sitting at the corrected name as its "target": conflict.filename is
    therefore the *invalid* name (used below to say what's being decided),
    while `new_filename` - passed separately since it's not what
    conflict.filename holds - is the corrected name that already exists.

    Attributes
    ----------
    resolution : ConflictResolution
        Set when the dialog is accepted; defaults to SKIP if rejected/closed.
    """

    def __init__(self, conflict: MoveConflict, new_filename: str, parent=None) -> None:
        super().__init__(parent)
        self._conflict = conflict
        self._new_filename = new_filename
        self.resolution = ConflictResolution.SKIP
        self.setWindowTitle("Dateikonflikt beim Umbenennen")
        self.setModal(True)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        headline = QLabel(
            f"<b>{self._new_filename}</b> existiert bereits im Sammelordner."
        )
        headline.setWordWrap(True)
        root.addWidget(headline)

        root.addWidget(
            build_conflict_table(self._conflict, "Umzubenennen", "Vorhanden")
        )
        root.addWidget(QLabel(f"Was soll mit '{self._conflict.filename}' passieren?"))
        root.addLayout(self._build_buttons())

    def _build_buttons(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._btn_overwrite = QPushButton("Neue übernehmen")
        self._btn_overwrite.setToolTip(
            "Vorhandene Datei durch die umbenannte Datei ersetzen."
        )

        self._btn_keep = QPushButton("Vorhandene behalten")
        self._btn_keep.setToolTip(
            "Vorhandene Datei behalten: die ungültig benannte Datei wird "
            "verworfen (gelöscht), z.B. bei einem Duplikat."
        )

        self._btn_skip = QPushButton("Überspringen")
        self._btn_skip.setToolTip(
            "Keine Aktion – die Datei behält ihren ungültigen Namen."
        )

        bar.addStretch()
        bar.addWidget(self._btn_overwrite)
        bar.addWidget(self._btn_keep)
        bar.addWidget(self._btn_skip)

        self._btn_overwrite.clicked.connect(self._accept_overwrite)
        self._btn_keep.clicked.connect(self._accept_keep)
        self._btn_skip.clicked.connect(self._accept_skip)

        return bar

    # ── slots ─────────────────────────────────────────────────────────────────

    def _accept_overwrite(self) -> None:
        self.resolution = ConflictResolution.OVERWRITE
        self.accept()

    def _accept_keep(self) -> None:
        self.resolution = ConflictResolution.KEEP_EXISTING
        self.accept()

    def _accept_skip(self) -> None:
        self.resolution = ConflictResolution.SKIP
        self.accept()
