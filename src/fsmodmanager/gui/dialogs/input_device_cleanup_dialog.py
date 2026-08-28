"""InputDeviceCleanupDialog – remove all action bindings for one input device.

New feature, no Java equivalent. FS's inputBinding.xml (living next to the
mods folder) never cleans up old per-device key/button/axis bindings when a
physical device (wheel, joystick, pedals, ...) is replaced or unplugged –
every <actionBinding> keeps a stale <binding device="..."> entry for it
forever. This dialog lists the devices FS has registered (by their real
product name, from inputBinding.xml's <devices> section) and lets the user
strip all of one device's bindings from the whole file in one go, with a
confirmation showing exactly how many entries will be removed and a note
that a backup is made first.

Usage
-----
    dialog = InputDeviceCleanupDialog(xml_path, parent=self)
    dialog.exec()
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from fsmodmanager.core.service.input_binding_service import (
    InputBindingError,
    InputDevice,
    list_devices,
    remove_device_bindings,
)

_DEVICE_ROLE = Qt.ItemDataRole.UserRole


class InputDeviceCleanupDialog(QDialog):
    """Modal dialog: pick a registered input device, remove all of its
    bindings from inputBinding.xml."""

    def __init__(self, xml_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._xml_path = xml_path
        self.setWindowTitle("Eingabegerät-Bindings entfernen")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        self._reload_devices()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        info = QLabel(
            f"Datei: {self._xml_path}\n\n"
            "Gerät auswählen: Alle Tasten-/Achsen-Zuordnungen dieses Geräts "
            "werden aus sämtlichen Action-Bindings entfernt. Das Gerät "
            "selbst bleibt registriert."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        root.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_remove = QPushButton("Bindings entfernen")
        self._btn_remove.setEnabled(False)
        btn_row.addWidget(self._btn_remove)
        btn_row.addStretch()
        root.addLayout(btn_row)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        root.addWidget(box)

        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._btn_remove.clicked.connect(self._on_remove_clicked)

    # ── data ──────────────────────────────────────────────────────────────────

    def _reload_devices(self) -> None:
        self._list.clear()
        try:
            devices = list_devices(self._xml_path)
        except InputBindingError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            self.reject()
            return

        if not devices:
            placeholder = QListWidgetItem("Keine registrierten Geräte gefunden.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
            return

        for device in devices:
            item = QListWidgetItem(device.name)
            item.setData(_DEVICE_ROLE, device)
            self._list.addItem(item)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        self._btn_remove.setEnabled(bool(self._list.selectedItems()))

    def _on_remove_clicked(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        device: InputDevice = items[0].data(_DEVICE_ROLE)

        try:
            preview_count = remove_device_bindings(
                self._xml_path, device.device_id, dry_run=True
            )
        except InputBindingError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            return

        if preview_count == 0:
            QMessageBox.information(
                self,
                "Eingabegerät-Bindings entfernen",
                f"Für '{device.name}' wurden keine Einträge gefunden.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Bindings entfernen",
            f"{preview_count} Eintrag/Einträge für '{device.name}' werden aus "
            f"'{self._xml_path.name}' entfernt.\n\n"
            f"Vor dem Speichern wird automatisch eine Sicherung "
            f"('{self._xml_path.name}.bak') angelegt.\n\nFortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            removed = remove_device_bindings(self._xml_path, device.device_id)
        except InputBindingError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            return

        QMessageBox.information(
            self,
            "Eingabegerät-Bindings entfernen",
            f"{removed} Eintrag/Einträge für '{device.name}' entfernt.",
        )
        self._reload_devices()
