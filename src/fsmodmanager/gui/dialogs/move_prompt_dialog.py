"""MovePromptDialog – shows a file-conflict prompt and returns the user's decision.

Replaces the inline QMessageBox in MainWindow._ask_resolve_conflict so that
the dialog logic is testable in isolation.

Usage
-----
    dialog = MovePromptDialog(conflict, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        resolution = dialog.resolution
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from fsmodmanager.core.service.collection_service import ConflictResolution, MoveConflict

_DATE_FMT = "%d.%m.%Y %H:%M"


class MovePromptDialog(QDialog):
    """Modal dialog that presents a MoveConflict and collects a ConflictResolution.

    Attributes
    ----------
    resolution : ConflictResolution
        Set when the dialog is accepted; defaults to SKIP if rejected/closed.
    """

    def __init__(self, conflict: MoveConflict, parent=None) -> None:
        super().__init__(parent)
        self._conflict = conflict
        self.resolution = ConflictResolution.SKIP
        self.setWindowTitle("Dateikonflikt")
        self.setModal(True)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # ── headline ──────────────────────────────────────────────────────────
        headline = QLabel(
            f"<b>{self._conflict.filename}</b> ist bereits im Sammelordner vorhanden."
        )
        headline.setWordWrap(True)
        root.addWidget(headline)

        # ── comparison table ──────────────────────────────────────────────────
        root.addWidget(self._build_table())

        # ── question ──────────────────────────────────────────────────────────
        root.addWidget(QLabel("Was soll mit der neuen Datei passieren?"))

        # ── buttons ───────────────────────────────────────────────────────────
        root.addLayout(self._build_buttons())

    def _build_table(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(frame)
        grid.setSpacing(8)

        c = self._conflict
        headers = ["", "Neu (Mod-Ordner)", "Vorhanden (Sammelordner)"]
        rows = [
            ("Version", c.source_version or "unbekannt", c.target_version or "unbekannt"),
            ("Größe", f"{c.source_size:,} Bytes", f"{c.target_size:,} Bytes"),
            ("Geändert", c.source_modified.strftime(_DATE_FMT), c.target_modified.strftime(_DATE_FMT)),
        ]

        for col, text in enumerate(headers):
            lbl = QLabel(f"<b>{text}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        for row_idx, (label, source_val, target_val) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row_idx, 0)
            grid.addWidget(QLabel(source_val), row_idx, 1, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(QLabel(target_val), row_idx, 2, Qt.AlignmentFlag.AlignCenter)

        return frame

    def _build_buttons(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._btn_overwrite = QPushButton("Neue übernehmen")
        self._btn_overwrite.setToolTip(
            "Vorhandene Datei ersetzen und Symlink auf die neue Datei setzen."
        )

        self._btn_keep = QPushButton("Vorhandene behalten")
        self._btn_keep.setToolTip(
            "Neue Datei verwerfen und Symlink auf die vorhandene Datei setzen."
        )

        self._btn_skip = QPushButton("Überspringen")
        self._btn_skip.setToolTip(
            "Keine Aktion – die neue Datei bleibt als echte Datei im Mod-Ordner."
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
