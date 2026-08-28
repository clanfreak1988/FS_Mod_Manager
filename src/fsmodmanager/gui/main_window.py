"""MainWindow – the application's primary window.

Layout
------
  ┌─ toolbar ──────────────────────────────────────────────────────────────────┐
  │ Konfiguration: [ComboBox] [Neu] [Umbenennen] [Kopieren] [Löschen]          │
  │   [Savegame importieren] [Eingabegeräte] [Einstellungen]                   │
  ├─ mod area ─────────────────────────────────────────────────────────────────┤
  │  Verfügbar              │  ← → ↔  │  Ausgewählt                            │
  │  [ModListWidget]        │  [→ ]   │  [ModListWidget]                       │
  │                         │  [⇒ ]   │                                        │
  │                         │  [← ]   │                                        │
  │                         │  [⇐ ]   │                                        │
  ├─ action bar ───────────────────────────────────────────────────────────────┤
  │  [Aktivieren]  [Speichern]  [Als ZIP exportieren]  Status: …                │
  └────────────────────────────────────────────────────────────────────────────┘

The window uses MainViewModel (MVVM) for all logic; widgets never call
Core services directly.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from PySide6.QtCore import QModelIndex, QPoint, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from fsmodmanager.core.app_paths import LOG_FILE
from fsmodmanager.core.model.mod import Mod, is_valid_mod_name
from fsmodmanager.core.service.collection_service import ConflictResolution, MoveConflict
from fsmodmanager.gui.dialogs.input_device_cleanup_dialog import InputDeviceCleanupDialog
from fsmodmanager.gui.dialogs.move_prompt_dialog import MovePromptDialog
from fsmodmanager.gui.dialogs.rename_conflict_dialog import RenameConflictDialog
from fsmodmanager.gui.dialogs.settings_dialog import SettingsDialog
from fsmodmanager.gui.icon import app_icon
from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel
from fsmodmanager.gui.widgets.mod_list_widget import ModListWidget


class MainWindow(QMainWindow):
    """Primary application window wired to MainViewModel."""

    def __init__(self, view_model: MainViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self.setWindowTitle("FS Mod Manager")
        self.setWindowIcon(app_icon())
        self.resize(1150, 700)

        self._build_ui()
        self._connect_vm()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addLayout(self._build_config_bar())
        root.addLayout(self._build_mod_area(), stretch=1)
        root.addLayout(self._build_action_bar())

    def _build_config_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(4)

        bar.addWidget(QLabel("Konfiguration:"))

        self._config_combo = QComboBox()
        self._config_combo.setMinimumWidth(220)
        self._config_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        bar.addWidget(self._config_combo)

        self._btn_new = QPushButton("Neu")
        self._btn_rename = QPushButton("Umbenennen")
        self._btn_copy = QPushButton("Kopieren")
        self._btn_delete = QPushButton("Löschen")
        self._btn_import_sg = QPushButton("Savegame importieren")
        self._btn_input_devices = QPushButton("Eingabegeräte")
        self._btn_input_devices.setToolTip(
            "Bindings eines Eingabegeräts (z.B. Lenkrad, Joystick) aus der "
            "inputBinding.xml entfernen."
        )
        self._btn_settings = QPushButton("Einstellungen")
        self._btn_reload = QPushButton("Neu laden")
        self._btn_info   = QPushButton("?")
        self._btn_info.setFixedWidth(28)
        self._btn_info.setMenu(self._build_info_menu())

        for btn in (
            self._btn_new,
            self._btn_rename,
            self._btn_copy,
            self._btn_delete,
            self._btn_import_sg,
            self._btn_input_devices,
            self._btn_settings,
            self._btn_reload,
            self._btn_info,
        ):
            bar.addWidget(btn)

        bar.addStretch()
        return bar

    def _build_mod_area(self) -> QHBoxLayout:
        area = QHBoxLayout()
        area.setSpacing(4)

        # ── left column (available mods) ──────────────────────────────────────
        left = QVBoxLayout()
        self._lbl_available = QLabel("Verfügbar")
        left.addWidget(self._lbl_available)
        self._search_available = QLineEdit()
        self._search_available.setPlaceholderText("Suchen…")
        self._search_available.setClearButtonEnabled(True)
        left.addWidget(self._search_available)
        self._available_list = ModListWidget()
        left.addWidget(self._available_list)

        # ── center button column ──────────────────────────────────────────────
        mid = QVBoxLayout()
        mid.setSpacing(4)
        mid.addStretch()
        self._btn_move_one_right = QPushButton("→")
        self._btn_move_all_right = QPushButton("⇒")
        self._btn_move_one_left = QPushButton("←")
        self._btn_move_all_left = QPushButton("⇐")
        for btn in (
            self._btn_move_one_right,
            self._btn_move_all_right,
            self._btn_move_one_left,
            self._btn_move_all_left,
        ):
            btn.setFixedWidth(40)
            mid.addWidget(btn)
        mid.addStretch()

        # ── right column (selected mods) ──────────────────────────────────────
        right = QVBoxLayout()
        self._lbl_selected = QLabel("Ausgewählt")
        right.addWidget(self._lbl_selected)
        self._search_selected = QLineEdit()
        self._search_selected.setPlaceholderText("Suchen…")
        self._search_selected.setClearButtonEnabled(True)
        right.addWidget(self._search_selected)
        self._selected_list = ModListWidget()
        right.addWidget(self._selected_list)

        area.addLayout(left, stretch=1)
        area.addLayout(mid)
        area.addLayout(right, stretch=1)
        return area

    def _build_action_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._btn_activate = QPushButton("Aktivieren")
        self._btn_save = QPushButton("Speichern")
        self._btn_export = QPushButton("Als ZIP exportieren")
        self._btn_export.setToolTip(
            "Alle Mods aus der Spalte 'Ausgewählt' in eine einzelne ZIP-Datei "
            "packen, um sie einfacher zu teilen."
        )
        self._btn_activate.setEnabled(False)
        self._btn_save.setEnabled(False)

        bar.addWidget(self._btn_activate)
        bar.addWidget(self._btn_save)
        bar.addWidget(self._btn_export)
        bar.addStretch()

        self._status_label = QLabel("Bereit")
        bar.addWidget(self._status_label)
        return bar

    # ── ViewModel connection ──────────────────────────────────────────────────

    def _connect_vm(self) -> None:
        vm = self._vm

        # ── ViewModel → UI ────────────────────────────────────────────────────
        vm.available_mods_changed.connect(self._on_available_mods_changed)
        vm.selected_mods_changed.connect(self._on_selected_mods_changed)
        vm.config_names_changed.connect(self._on_config_names_changed)
        vm.active_config_changed.connect(self._on_active_config_changed)
        vm.status_changed.connect(self._on_status_changed)
        vm.error_occurred.connect(self._on_error_occurred)
        vm.conflicts_detected.connect(self._on_conflicts_detected)
        vm.warning_occurred.connect(self._on_warning_occurred)
        vm.new_mods_detected.connect(self._on_new_mods_detected)
        self._btn_reload.clicked.connect(self._vm.reload)

        # ── Config-bar buttons ────────────────────────────────────────────────
        self._btn_new.clicked.connect(self._on_new_config)
        self._btn_rename.clicked.connect(self._on_rename_config)
        self._btn_copy.clicked.connect(self._on_copy_config)
        self._btn_delete.clicked.connect(self._on_delete_config)
        self._btn_import_sg.clicked.connect(self._on_import_savegame)
        self._btn_input_devices.clicked.connect(self._on_cleanup_input_devices)
        self._btn_settings.clicked.connect(self._on_open_settings)
        # textActivated fires on every user click – even when the same item is
        # re-selected.  currentTextChanged would silently skip that case and leave
        # the ViewModel out-of-sync with what the ComboBox displays.
        self._config_combo.textActivated.connect(self._on_combo_changed)

        # ── Move buttons ──────────────────────────────────────────────────────
        self._btn_move_one_right.clicked.connect(self._on_move_one_right)
        self._btn_move_all_right.clicked.connect(self._vm.move_all_to_selected)
        self._btn_move_one_left.clicked.connect(self._on_move_one_left)
        self._btn_move_all_left.clicked.connect(self._vm.move_all_to_available)

        # ── Search fields ─────────────────────────────────────────────────────
        self._search_available.textChanged.connect(self._available_list.set_filter)
        self._search_selected.textChanged.connect(self._selected_list.set_filter)

        # ── Double-click to move ──────────────────────────────────────────────
        self._available_list.doubleClicked.connect(self._on_available_double_clicked)
        self._selected_list.doubleClicked.connect(self._on_selected_double_clicked)

        # ── Drag-and-drop between lists ───────────────────────────────────────
        self._selected_list.list_model.mods_dropped.connect(self._on_drop_to_selected)
        self._available_list.list_model.mods_dropped.connect(self._on_drop_to_available)

        # ── Right-click: offer to fix an invalid mod filename ─────────────────
        for list_widget in (self._available_list, self._selected_list):
            list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(
                lambda point, lw=list_widget: self._on_mod_context_menu(lw, point)
            )

        # ── Action-bar buttons ────────────────────────────────────────────────
        self._btn_activate.clicked.connect(self._vm.activate_config)
        self._btn_save.clicked.connect(self._vm.save_config)
        self._btn_export.clicked.connect(self._on_export)

    # ── slots: ViewModel → UI ─────────────────────────────────────────────────

    @Slot(list)
    def _on_available_mods_changed(self, mods: list[Mod]) -> None:
        self._available_list.set_mods(mods)
        self._lbl_available.setText(f"Verfügbar ({len(mods)})")

    @Slot(list)
    def _on_selected_mods_changed(self, mods: list[Mod]) -> None:
        self._selected_list.set_mods(mods)
        self._lbl_selected.setText(f"Ausgewählt ({len(mods)})")

    @Slot(list)
    def _on_config_names_changed(self, names: list[str]) -> None:
        current = self._config_combo.currentText()
        self._config_combo.blockSignals(True)
        self._config_combo.clear()
        self._config_combo.addItems(names)
        idx = self._config_combo.findText(current)
        if idx >= 0:
            self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)

    @Slot(str)
    def _on_active_config_changed(self, name: str) -> None:
        self._config_combo.blockSignals(True)
        idx = self._config_combo.findText(name)
        if idx >= 0:
            self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)
        has_config = bool(name)
        self._btn_save.setEnabled(has_config)
        self._btn_activate.setEnabled(has_config)

    @Slot(str)
    def _on_status_changed(self, message: str) -> None:
        self._status_label.setText(message)

    @Slot(str)
    def _on_error_occurred(self, message: str) -> None:
        QMessageBox.critical(self, "Fehler", message)

    @Slot(list)
    def _on_conflicts_detected(self, conflicts: list[MoveConflict]) -> None:
        for conflict in conflicts:
            self._ask_resolve_conflict(conflict)

    # ── slots: config-bar buttons ─────────────────────────────────────────────

    @Slot()
    def _on_new_config(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Neue Konfiguration")
        dialog.setMinimumWidth(360)
        vbox = QVBoxLayout(dialog)

        hint = QLabel(
            "Nur Buchstaben (a–z, A–Z) und Ziffern (0–9) erlaubt.\n"
            "Keine Leerzeichen oder Sonderzeichen."
        )
        hint.setWordWrap(True)
        vbox.addWidget(hint)

        edit = QLineEdit()
        edit.setPlaceholderText("Konfigurationsname")
        vbox.addWidget(edit)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(False)
        box.accepted.connect(dialog.accept)
        box.rejected.connect(dialog.reject)
        vbox.addWidget(box)

        existing = set(self._vm._config_svc.list_names())

        def _validate(text: str) -> None:
            ok_btn.setEnabled(
                bool(re.fullmatch(r"[a-zA-Z0-9]+", text)) and text not in existing
            )

        edit.textChanged.connect(_validate)

        if dialog.exec() == QDialog.DialogCode.Accepted and edit.text():
            self._vm.create_config(edit.text())

    @Slot()
    def _on_rename_config(self) -> None:
        old_name = self._config_combo.currentText()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(
            self, "Umbenennen", "Neuer Name:", text=old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            self._vm.rename_config(old_name, new_name.strip())

    @Slot()
    def _on_copy_config(self) -> None:
        source = self._config_combo.currentText()
        if not source:
            return
        target, ok = QInputDialog.getText(
            self, "Kopieren", "Name der Kopie:", text=f"{source}_Kopie"
        )
        if ok and target.strip():
            self._vm.copy_config(source, target.strip())

    @Slot()
    def _on_delete_config(self) -> None:
        name = self._config_combo.currentText()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Löschen",
            f"Konfiguration '{name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.delete_config(name)

    @Slot()
    def _on_import_savegame(self) -> None:
        """Scan savegame_path for savegame[0-9]+ folders and let user pick one.

        Mirrors Java ModPacks.listSavegameFolder + dialogGui(saveGameContext=True):
        the user selects a savegame name from a list; the XML path is built
        internally as <savegame_path>/<name>/careerSavegame.xml.
        Falls back to a file picker when no savegame folders are found.
        """
        import re
        savegame_base = (
            Path(self._vm.settings.savegame_path) if self._vm.settings else Path.home()
        )

        # Collect folders matching savegame\d+
        savegame_dirs: list[str] = []
        if savegame_base.is_dir():
            savegame_dirs = sorted(
                d.name
                for d in savegame_base.iterdir()
                if d.is_dir() and re.fullmatch(r"savegame\d+", d.name)
            )

        if savegame_dirs:
            name, ok = QInputDialog.getItem(
                self,
                "Savegame auswählen",
                "Welches Savegame soll ausgelesen werden?",
                savegame_dirs,
                editable=False,
            )
            if ok and name:
                xml_path = savegame_base / name / "careerSavegame.xml"
                if not xml_path.exists():
                    QMessageBox.warning(
                        self, "Savegame",
                        f"careerSavegame.xml nicht gefunden in:\n{xml_path.parent}"
                    )
                    return
                self._vm.import_savegame(xml_path)
        else:
            # Fallback: let user pick the XML file directly
            xml_str, _ = QFileDialog.getOpenFileName(
                self,
                "careerSavegame.xml öffnen",
                str(savegame_base),
                "Savegame XML (careerSavegame.xml);;XML-Dateien (*.xml)",
            )
            if xml_str:
                self._vm.import_savegame(Path(xml_str))

    @Slot()
    def _on_cleanup_input_devices(self) -> None:
        """Open the input-device binding cleanup dialog.

        inputBinding.xml lives next to the mods folder, i.e. one level up
        from source_mod_folder (<gameHome>/inputBinding.xml,
        <gameHome>/mods, <gameHome>/LS_mods, ...).
        """
        if self._vm.settings is None:
            return
        xml_path = Path(self._vm.settings.source_mod_folder).parent / "inputBinding.xml"
        if not xml_path.is_file():
            QMessageBox.information(
                self,
                "Eingabegeräte",
                f"Keine inputBinding.xml gefunden unter:\n{xml_path}",
            )
            return
        dialog = InputDeviceCleanupDialog(xml_path, parent=self)
        dialog.exec()

    @Slot()
    def _on_export(self) -> None:
        """Bundle the current "Ausgewählt" selection into one ZIP for sharing.

        Always asks where to save via a file dialog, as requested – there is
        no remembered/default export location.
        """
        if not self._vm.selected_mods:
            QMessageBox.information(
                self,
                "Exportieren",
                "Es sind keine Mods in der Spalte 'Ausgewählt', die exportiert werden könnten.",
            )
            return

        suggested_name = f"{self._vm.active_config_name or 'mods'}.zip"
        start_path = str(Path.home() / suggested_name)
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Mods als ZIP exportieren",
            start_path,
            "ZIP-Archiv (*.zip)",
        )
        if not path_str:
            return  # user cancelled

        target = Path(path_str)
        if target.suffix.lower() != ".zip":
            target = target.with_suffix(".zip")
        self._vm.export_selected_mods(target)

    @Slot()
    def _on_open_settings(self) -> None:
        if self._vm.settings is None:
            return
        old_settings = self._vm.settings
        dialog = SettingsDialog(old_settings, parent=self)
        if dialog.exec():
            new_settings = dialog.settings
            self._move_folders_if_changed(old_settings, new_settings)
            self._vm.save_settings(new_settings)
            # Re-initialize so the new paths are picked up fully
            # (collection scan, config service path, etc.)
            self._vm.initialize()
            self._update_after_init()

    def _move_folders_if_changed(self, old_settings, new_settings) -> None:
        """Offer to physically move mod files when Settings paths changed.

        Mirrors Java's changeModFolders(): only relocating the *setting*
        would silently strand existing mods at the old path.
        """
        old_collection = old_settings.mod_collection_folder
        new_collection = new_settings.mod_collection_folder
        if old_collection != new_collection:
            reply = QMessageBox.question(
                self,
                "Verschiebung des gesammelten Mods Ordners?",
                "Sollen die Mods aus dem Sammelordner verschoben werden? "
                "Aufgrund der Anzahl der Mods, kann dieser Vorgang einige Zeit "
                "in Anspruch nehmen\n\n"
                f"Ursprünglicher Pfad: {old_collection}\n\n"
                f"Neuer Pfad: {new_collection}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                failed = self._vm.move_collection_folder(Path(old_collection), Path(new_collection))
                if failed:
                    QMessageBox.warning(
                        self, "Sammelordner",
                        "Folgende Mods konnten nicht verschoben werden:\n" + "\n".join(failed),
                    )

        old_source = old_settings.source_mod_folder
        new_source = new_settings.source_mod_folder
        if old_source != new_source:
            reply = QMessageBox.question(
                self,
                "Verschiebung der Mods?",
                "Sollen die Mods verschoben werden?\n\n"
                f"Ursprünglicher Pfad: {old_source}\n\n"
                f"Neuer Pfad: {new_source}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                failed = self._vm.move_source_folder(
                    Path(old_source), Path(new_source), Path(new_collection)
                )
                if failed:
                    QMessageBox.warning(
                        self, "Mod-Ordner",
                        "Folgende Mods konnten nicht verschoben werden:\n" + "\n".join(failed),
                    )

    @Slot(str)
    def _on_combo_changed(self, name: str) -> None:
        if name:
            self._vm.select_config(name)

    # ── slots: move buttons ───────────────────────────────────────────────────

    @Slot()
    def _on_move_one_right(self) -> None:
        mods = self._available_list.selected_mods()
        if mods:
            self._vm.move_to_selected(mods)

    @Slot()
    def _on_move_one_left(self) -> None:
        mods = self._selected_list.selected_mods()
        if mods:
            self._vm.move_to_available(mods)

    # ── slots: drag-and-drop ──────────────────────────────────────────────────

    @Slot(list)
    def _on_drop_to_selected(self, filenames: list[str]) -> None:
        """Filenames dropped onto the selected list → move from available."""
        fn_set = set(filenames)
        mods = [m for m in self._vm.available_mods if m.filename in fn_set]
        if mods:
            self._vm.move_to_selected(mods)

    @Slot(list)
    def _on_drop_to_available(self, filenames: list[str]) -> None:
        """Filenames dropped onto the available list → move from selected."""
        fn_set = set(filenames)
        mods = [m for m in self._vm.selected_mods if m.filename in fn_set]
        if mods:
            self._vm.move_to_available(mods)

    # ── slots: double-click to move ───────────────────────────────────────────

    @Slot(QModelIndex)
    def _on_available_double_clicked(self, index: QModelIndex) -> None:
        mod = self._available_list.list_model.mod_at(index)
        if mod:
            self._vm.move_to_selected([mod])

    @Slot(QModelIndex)
    def _on_selected_double_clicked(self, index: QModelIndex) -> None:
        mod = self._selected_list.list_model.mod_at(index)
        if mod:
            self._vm.move_to_available([mod])

    @Slot(str)
    def _on_warning_occurred(self, message: str) -> None:
        QMessageBox.warning(self, "Warnung", message)

    @Slot(list)
    def _on_new_mods_detected(self, filenames: list[str]) -> None:
        # Highlight in both lists (matches Java's existingModsTV/selectedModsTV
        # row factories, which both check the same newMods set). Otherwise a
        # mod's highlight silently disappears while it sits in "Ausgewählt"
        # and reappears out of nowhere the moment it lands back in
        # "Verfügbar" - e.g. when select_config() moves mods between lists.
        highlighted = set(filenames)
        self._available_list.list_model.set_highlighted(highlighted)
        self._selected_list.list_model.set_highlighted(highlighted)

    @Slot()
    def _build_info_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Info", self._on_info)
        menu.addSeparator()
        menu.addAction("Log-Datei öffnen", self._on_open_log_file)
        menu.addAction("Log-Ordner öffnen", self._on_open_log_folder)
        return menu

    def _on_info(self) -> None:
        QMessageBox.information(
            self,
            "Info",
            "FS Mod Manager\n\nPython/PySide6 Port des LS Mod Managers.\n\nVersion: 1.0",
        )

    def _on_open_log_file(self) -> None:
        if not LOG_FILE.exists():
            QMessageBox.warning(self, "Log-Datei", f"Log-Datei nicht gefunden:\n{LOG_FILE}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_FILE)))

    def _on_open_log_folder(self) -> None:
        if not LOG_FILE.parent.exists():
            QMessageBox.warning(self, "Log-Ordner", f"Log-Ordner nicht gefunden:\n{LOG_FILE.parent}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_FILE.parent)))

    # ── conflict resolution dialog ────────────────────────────────────────────

    def _ask_resolve_conflict(self, conflict: MoveConflict) -> None:
        dialog = MovePromptDialog(conflict, parent=self)
        dialog.exec()
        self._vm.resolve_conflict(conflict, dialog.resolution)

    # ── mod context menu (rename / delete) ────────────────────────────────────

    def _on_mod_context_menu(self, list_widget: ModListWidget, point: QPoint) -> None:
        index = list_widget.indexAt(point)
        mod = list_widget.list_model.mod_at(index)
        if mod is None:
            return
        menu = self._build_mod_context_menu(mod)
        menu.exec(list_widget.viewport().mapToGlobal(point))

    def _build_mod_context_menu(self, mod: Mod) -> QMenu:
        """Split out from _on_mod_context_menu() so tests can inspect the
        menu's contents without invoking the real (blocking, unpatchable in
        PySide6) QMenu.exec()."""
        menu = QMenu(self)
        if mod.has_invalid_name:
            menu.addAction("Datei richtig benennen…", lambda: self._on_rename_mod(mod))
        menu.addAction("Löschen…", lambda: self._on_delete_mod(mod))
        return menu

    def _on_delete_mod(self, mod: Mod) -> None:
        reply = QMessageBox.question(
            self,
            "Löschen",
            f"'{mod.title or mod.filename}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._vm.delete_mod(mod)

    def _on_rename_mod(self, mod: Mod) -> None:
        new_filename = self._vm.suggest_valid_mod_name(mod.filename)
        while True:
            text, ok = QInputDialog.getText(
                self,
                "Mod umbenennen",
                f"Neuer Dateiname für '{mod.filename}':",
                QLineEdit.EchoMode.Normal,
                new_filename,
            )
            if not ok:
                return
            new_filename = text.strip()
            if not new_filename.lower().endswith(".zip"):
                new_filename += ".zip"
            if is_valid_mod_name(new_filename):
                break
            QMessageBox.warning(
                self, "Ungültiger Name",
                "Der Name enthält weiterhin ungültige Zeichen. Erlaubt sind nur "
                "Buchstaben, Ziffern und Unterstrich (_); das erste Zeichen darf "
                "keine Ziffer sein.",
            )

        resolution = ConflictResolution.OVERWRITE
        conflict = self._vm.check_rename_conflict(mod, new_filename)
        if conflict is not None:
            dialog = RenameConflictDialog(conflict, new_filename, parent=self)
            dialog.exec()
            resolution = dialog.resolution
        self._vm.rename_mod(mod, new_filename, resolution=resolution)

    # ── initialise on show ────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Save window dimensions on close."""
        if self._vm.settings:
            s = copy.copy(self._vm.settings)
            s.scene_width = float(self.width())
            s.scene_height = float(self.height())
            self._vm.save_settings(s)
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not hasattr(self, "_initialized"):
            self._initialized = True
            # Defer by one event-loop tick so the main window is fully visible
            # before any child dialogs are opened.
            QTimer.singleShot(0, self._do_initialize)

    def _do_initialize(self) -> None:
        first_run = not self._vm._settings_svc.exists()
        self._vm.initialize()

        if first_run and self._vm.settings:
            dialog = SettingsDialog(self._vm.settings, first_run=True, parent=self)
            if dialog.exec():
                self._vm.save_settings(dialog.settings)
                self._vm.initialize()

        # One-time prompt: import all savegames as configs
        if self._vm.settings and not self._vm.settings.savegames_read:
            reply = QMessageBox.question(
                self,
                "Konfigurationen aus Savegames",
                "Sollen aus den vorhandenen Savegames Konfigurationen erstellt werden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._vm.import_all_savegames()
            s = copy.copy(self._vm.settings)
            s.savegames_read = True
            self._vm.save_settings(s)

        self._update_after_init()

    def _update_after_init(self) -> None:
        """Update widgets that depend on fully resolved settings."""
        if self._vm.settings:
            coll = Path(self._vm.settings.mod_collection_folder)
            self._available_list.set_collection_dir(coll)
            self._selected_list.set_collection_dir(coll)

        # Restore saved window size
        if self._vm.settings:
            w = max(800, int(self._vm.settings.scene_width))
            h = max(600, int(self._vm.settings.scene_height))
            self.resize(w, h)

        # Populate the combo.  _on_config_names_changed falls back to the
        # combo's *current* text when choosing which item to keep selected.
        # At startup the combo is still empty so that heuristic picks nothing
        # and the first alphabetical entry ends up shown – even if a different
        # config is already active in the ViewModel.  We therefore set the
        # combo explicitly to the VM's active config afterwards.
        self._on_config_names_changed(self._vm._config_svc.list_names())
        active = self._vm.active_config_name
        self._config_combo.blockSignals(True)
        idx = self._config_combo.findText(active) if active else -1
        # QComboBox.addItems() on a still-empty combo auto-selects index 0;
        # without this, no active config would still show one selected.
        self._config_combo.setCurrentIndex(idx)
        self._config_combo.blockSignals(False)
