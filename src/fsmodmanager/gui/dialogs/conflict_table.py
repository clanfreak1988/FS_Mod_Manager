"""Shared comparison grid for the two file-conflict dialogs.

MovePromptDialog (a collect()-time collision between the FS mods folder and
the collection folder) and RenameConflictDialog (a same-folder rename onto an
existing file) present the same MoveConflict fields in the same three-row
table and differ only in how they word the two column headings.

Keeping the grid here means the column order - incoming file left, existing
file right, matching the button order "Neue übernehmen" / "Vorhandene
behalten" - is defined once and cannot drift apart between the dialogs.

Usage
-----
    root.addWidget(build_conflict_table(conflict, "Neu", "Vorhanden"))
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel

from fsmodmanager.core.service.collection_service import MoveConflict

_DATE_FMT = "%d.%m.%Y %H:%M"

_ROW_LABELS = ("Version", "Größe", "Geändert")


def _column(version: str, size: int, modified: datetime) -> tuple[str, str, str]:
    """One file's cells, in _ROW_LABELS order."""
    return (
        version or "unbekannt",
        f"{size:,} Bytes",
        modified.strftime(_DATE_FMT),
    )


def build_conflict_table(
    conflict: MoveConflict, new_header: str, existing_header: str
) -> QFrame:
    """Build the Version/Größe/Geändert comparison grid for `conflict`.

    In both dialogs the conflict's *source* is the incoming file and its
    *target* the one already in place; they are rendered in that order, each
    header travelling with the values it labels.
    """
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    grid = QGridLayout(frame)
    grid.setSpacing(8)

    for row_idx, label in enumerate(_ROW_LABELS, start=1):
        grid.addWidget(QLabel(label), row_idx, 0)

    columns = [
        (
            new_header,
            _column(
                conflict.source_version, conflict.source_size, conflict.source_modified
            ),
        ),
        (
            existing_header,
            _column(
                conflict.target_version, conflict.target_size, conflict.target_modified
            ),
        ),
    ]

    for col, (header, values) in enumerate(columns, start=1):
        for row_idx, text in enumerate((f"<b>{header}</b>", *values)):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, row_idx, col)

    return frame
