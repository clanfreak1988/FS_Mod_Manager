"""NewModsAssignDialog – assign freshly collected mods to configurations.

New feature, no Java equivalent. After startup's collect() moves new mod ZIPs
into the collection folder, they are only highlighted in the lists; getting
them into a configuration meant selecting each config and moving the mods
over by hand, one config at a time.

This dialog shows a checkbox matrix instead: one row per new mod, one column
per saved configuration. A mod can therefore go into several configs and a
config can receive several mods in a single pass - including "alles ankreuzen"
for every new mod in every config.

Usage
-----
    dialog = NewModsAssignDialog(new_mods, config_names, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        vm.assign_mods_to_configs(dialog.assignments)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from fsmodmanager.core.model.mod import Mod


class NewModsAssignDialog(QDialog):
    """Modal matrix dialog: which of the new mods go into which configs.

    Attributes
    ----------
    assignments : dict[str, list[str]]
        Config name → mod filenames ticked for it. Only non-empty entries are
        included, so an untouched dialog yields an empty dict.
    """

    def __init__(self, mods: list[Mod], config_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self._mods = list(mods)
        self._config_names = list(config_names)
        self.setWindowTitle("Neue Mods gefunden")
        self.setModal(True)
        self.setMinimumSize(640, 400)
        self._build_ui()

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def assignments(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for col, name in enumerate(self._config_names):
            filenames = [
                mod.filename
                for row, mod in enumerate(self._mods)
                if self._table.item(row, col).checkState() == Qt.CheckState.Checked
            ]
            if filenames:
                result[name] = filenames
        return result

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        headline = QLabel(
            f"<b>{len(self._mods)} neue Mod(s)</b> wurden in den Sammelordner "
            "übernommen. Ankreuzen, zu welchen Konfigurationen sie hinzugefügt "
            "werden sollen."
        )
        headline.setWordWrap(True)
        root.addWidget(headline)

        hint = QLabel(
            "Ein Klick auf einen Spaltenkopf setzt/entfernt die ganze Spalte "
            "(alle Mods in dieser Konfiguration), ein Klick auf einen Zeilenkopf "
            "die ganze Zeile (dieser Mod in allen Konfigurationen)."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        root.addWidget(self._build_table())
        root.addLayout(self._build_buttons())

    def _build_table(self) -> QTableWidget:
        self._table = QTableWidget(len(self._mods), len(self._config_names))
        self._table.setHorizontalHeaderLabels(self._config_names)
        # Maps are marked because a configuration can only ever hold one:
        # ticking a new map everywhere gets refused for every config that
        # already has one.
        self._table.setVerticalHeaderLabels(
            [
                f"{mod.title or mod.filename}{' (Karte)' if mod.is_map else ''}"
                for mod in self._mods
            ]
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for row, mod in enumerate(self._mods):
            self._table.verticalHeaderItem(row).setToolTip(mod.filename)
            for col in range(len(self._config_names)):
                item = QTableWidgetItem()
                item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)

        h_header = self._table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h_header.setSectionsClickable(True)
        h_header.sectionClicked.connect(self._on_column_header_clicked)

        v_header = self._table.verticalHeader()
        v_header.setSectionsClickable(True)
        v_header.sectionClicked.connect(self._on_row_header_clicked)

        return self._table

    def _build_buttons(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._btn_all = QPushButton("Alle Mods zu allen Konfigurationen")
        self._btn_all.setToolTip("Jedes Kästchen ankreuzen.")
        self._btn_none = QPushButton("Auswahl aufheben")

        self._btn_apply = QPushButton("Hinzufügen")
        self._btn_apply.setDefault(True)
        self._btn_skip = QPushButton("Überspringen")
        self._btn_skip.setToolTip(
            "Nichts zuordnen – die neuen Mods bleiben nur in der Sammlung."
        )

        bar.addWidget(self._btn_all)
        bar.addWidget(self._btn_none)
        bar.addStretch()
        bar.addWidget(self._btn_apply)
        bar.addWidget(self._btn_skip)

        self._btn_all.clicked.connect(lambda: self._set_all(True))
        self._btn_none.clicked.connect(lambda: self._set_all(False))
        self._btn_apply.clicked.connect(self.accept)
        self._btn_skip.clicked.connect(self.reject)

        return bar

    # ── slots ─────────────────────────────────────────────────────────────────

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self._table.rowCount()):
            for col in range(self._table.columnCount()):
                self._table.item(row, col).setCheckState(state)

    def _on_column_header_clicked(self, col: int) -> None:
        """Toggle a whole config column: tick it unless it's already full."""
        items = [self._table.item(row, col) for row in range(self._table.rowCount())]
        self._toggle(items)

    def _on_row_header_clicked(self, row: int) -> None:
        """Toggle a whole mod row across every config."""
        items = [self._table.item(row, col) for col in range(self._table.columnCount())]
        self._toggle(items)

    @staticmethod
    def _toggle(items: list[QTableWidgetItem]) -> None:
        all_checked = all(
            item.checkState() == Qt.CheckState.Checked for item in items
        )
        state = Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked
        for item in items:
            item.setCheckState(state)
