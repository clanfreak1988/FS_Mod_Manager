"""ProfileEditDialog – create or edit one game profile (FS installation).

New feature, no Java equivalent. Data in, data out like SettingsDialog: the
dialog never touches the ViewModel, it just hands back a GameProfile that the
caller passes to add_profile()/update_active_profile().

For a new profile a template combo pre-fills name and all three paths from
the standard layout of the chosen FS release, so adding a second installation
is usually just "Vorlage wählen → Anlegen".

Usage
-----
    dialog = ProfileEditDialog(existing_names=vm.profile_names, parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        vm.add_profile(dialog.profile)
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
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

from fsmodmanager.core.model.game_profile import GameProfile
from fsmodmanager.core.service.settings_service import (
    FS_VERSIONS,
    default_game_home,
    default_profile,
)

_GREEN = "color: green; font-weight: bold;"
_RED   = "color: red;  font-weight: bold;"


class ProfileEditDialog(QDialog):
    """Modal editor for a single game profile.

    Parameters
    ----------
    profile : GameProfile | None
        The profile to edit; None creates a new one (template combo shown).
    existing_names : list[str]
        Names already taken, so a clash is caught before the ViewModel
        rejects it. The edited profile's own name is expected to be absent.
    parent :
        Qt parent widget.

    Attributes
    ----------
    profile : GameProfile
        The edited profile, valid once the dialog was accepted.
    """

    def __init__(
        self,
        profile: GameProfile | None = None,
        *,
        existing_names: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._is_new = profile is None
        self._original = profile
        self._existing = [n.casefold() for n in (existing_names or [])]
        self.profile: GameProfile | None = profile
        self.setWindowTitle(
            "Neue Spielversion" if self._is_new else f"Spielversion '{profile.name}'"
        )
        self.setMinimumWidth(560)
        self.setModal(True)
        self._build_ui()
        self._populate()
        self._refresh_validation()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        if self._is_new:
            root.addWidget(self._build_template_row())

        root.addWidget(self._build_form_group())

        hint = QLabel(
            "Jede Spielversion braucht einen eigenen Mod- und Sammelordner. "
            "Das Ändern der Pfade verschiebt keine Dateien."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        root.addWidget(self._build_button_box())

    def _build_template_row(self) -> QGroupBox:
        group = QGroupBox("Vorlage")
        row = QHBoxLayout(group)
        row.setSpacing(6)

        self._combo_template = QComboBox()
        for label, _year in FS_VERSIONS:
            self._combo_template.addItem(label)
        row.addWidget(self._combo_template, stretch=1)

        btn = QPushButton("Pfade vorbelegen")
        btn.setToolTip(
            "Name und Pfade aus dem Standard-Ordner dieser FS-Version "
            "übernehmen (Dokumente/My Games/FarmingSimulator…)."
        )
        btn.clicked.connect(self._apply_template)
        row.addWidget(btn)

        return group

    def _build_form_group(self) -> QGroupBox:
        group = QGroupBox("Spielversion")
        form = QFormLayout(group)
        form.setSpacing(8)

        self._edit_name       = QLineEdit()
        self._edit_source     = QLineEdit()
        self._edit_collection = QLineEdit()
        self._edit_savegame   = QLineEdit()

        self._lbl_name       = QLabel("Name:")
        self._lbl_source     = QLabel("FS Mod-Ordner:")
        self._lbl_collection = QLabel("Sammelordner:")
        self._lbl_savegame   = QLabel("Savegame-Pfad:")

        for edit in (
            self._edit_name,
            self._edit_source,
            self._edit_collection,
            self._edit_savegame,
        ):
            edit.textChanged.connect(self._refresh_validation)

        form.addRow(self._lbl_name, self._edit_name)
        form.addRow(self._lbl_source, self._path_row(self._edit_source, self._browse_source))
        form.addRow(
            self._lbl_collection,
            self._path_row(
                self._edit_collection, self._browse_collection, self._btn_create_collection()
            ),
        )
        form.addRow(self._lbl_savegame, self._path_row(self._edit_savegame, self._browse_savegame))

        return group

    def _btn_create_collection(self) -> QPushButton:
        """Extra button on the collection row.

        Unlike the game's own folders the collection folder belongs to this
        application - on a freshly installed second FS version it simply
        doesn't exist yet, and requiring the user to leave the dialog and
        create it by hand would be the only thing standing between them and
        a working profile.
        """
        self._btn_mkdir = QPushButton("Anlegen")
        self._btn_mkdir.setToolTip("Sammelordner jetzt erstellen.")
        self._btn_mkdir.clicked.connect(self._create_collection_dir)
        return self._btn_mkdir

    def _build_button_box(self) -> QDialogButtonBox:
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Anlegen" if self._is_new else "Speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        return box

    @staticmethod
    def _path_row(edit: QLineEdit, browse_slot, extra: QPushButton | None = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(edit, stretch=1)
        btn = QPushButton("…")
        btn.setFixedWidth(30)
        btn.setToolTip("Ordner wählen")
        btn.clicked.connect(browse_slot)
        row.addWidget(btn)
        if extra is not None:
            row.addWidget(extra)
        return row

    # ── populate / extract ────────────────────────────────────────────────────

    def _populate(self) -> None:
        if self._original is None:
            self._apply_template()
            return
        self._edit_name.setText(self._original.name)
        self._edit_source.setText(self._original.source_mod_folder)
        self._edit_collection.setText(self._original.mod_collection_folder)
        self._edit_savegame.setText(self._original.savegame_path)

    def _apply_template(self) -> None:
        label, year = FS_VERSIONS[self._combo_template.currentIndex()]
        template = default_profile(f"FS{year[-2:]}", default_game_home(year))
        self._edit_name.setText(template.name)
        self._edit_source.setText(template.source_mod_folder)
        self._edit_collection.setText(template.mod_collection_folder)
        self._edit_savegame.setText(template.savegame_path)

    def _read_form(self) -> GameProfile:
        return GameProfile(
            name=self._edit_name.text().strip(),
            source_mod_folder=self._edit_source.text().strip(),
            mod_collection_folder=self._edit_collection.text().strip(),
            savegame_path=self._edit_savegame.text().strip(),
        )

    # ── validation ────────────────────────────────────────────────────────────

    def _refresh_validation(self) -> None:
        """Colour the labels and gate OK on everything being usable."""
        name = self._edit_name.text().strip()
        name_ok = bool(name) and name.casefold() not in self._existing
        self._lbl_name.setStyleSheet(_GREEN if name_ok else _RED)

        def _check(edit: QLineEdit, label: QLabel) -> bool:
            exists = Path(edit.text().strip()).is_dir() if edit.text().strip() else False
            label.setStyleSheet(_GREEN if exists else _RED)
            return exists

        ok_source     = _check(self._edit_source, self._lbl_source)
        ok_collection = _check(self._edit_collection, self._lbl_collection)
        ok_savegame   = _check(self._edit_savegame, self._lbl_savegame)

        self._btn_mkdir.setEnabled(
            bool(self._edit_collection.text().strip()) and not ok_collection
        )
        self._ok_btn.setEnabled(
            name_ok and ok_source and ok_collection and ok_savegame
        )

    # ── slots ─────────────────────────────────────────────────────────────────

    def _create_collection_dir(self) -> None:
        raw = self._edit_collection.text().strip()
        if not raw:
            return
        try:
            Path(raw).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Sammelordner", f"Ordner konnte nicht angelegt werden:\n{exc}"
            )
            return
        self._refresh_validation()

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

    def _on_accept(self) -> None:
        self.profile = self._read_form()
        self.accept()
