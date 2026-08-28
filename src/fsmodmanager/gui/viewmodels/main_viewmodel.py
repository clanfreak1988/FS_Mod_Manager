"""MainViewModel – single source of truth for the GUI.

Signals/Slots contract (enforced here, never broken by widgets):
  • Widgets NEVER call Core services directly.
  • Widgets call ViewModel methods (slots).
  • ViewModel emits signals when state changes.
  • Widgets connect to signals and update themselves.

Dependency injection via __init__ keeps everything testable without a display.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

from fsmodmanager.core.model.configuration import Configuration
from fsmodmanager.core.model.mod import Mod, is_valid_mod_name, sanitize_mod_name
from fsmodmanager.core.model.settings import Settings
from fsmodmanager.core.parser.mod_parser import ModParseError, parse_mod
from fsmodmanager.core.parser.savegame_parser import SavegameParseError, parse_savegame
from fsmodmanager.core.service.collection_service import (
    CollectionService,
    ConflictResolution,
    MoveConflict,
)
from fsmodmanager.core.service.config_service import (
    ConfigAlreadyExistsError,
    ConfigNotFoundError,
    ConfigService,
)
from fsmodmanager.core.service.export_service import ExportError, ExportService
from fsmodmanager.core.service.folder_move_service import FolderMoveService
from fsmodmanager.core.service.link_service import LinkError, LinkService
from fsmodmanager.core.service.mod_rename_service import ModRenameService
from fsmodmanager.core.service.settings_service import SettingsService


class MainViewModel(QObject):
    """Holds all GUI-visible state and wraps every Core operation.

    Signals
    -------
    available_mods_changed(list[Mod])
        Emitted when the left-column mod list changes.
    selected_mods_changed(list[Mod])
        Emitted when the right-column mod list changes.
    config_names_changed(list[str])
        Emitted when the set of saved configurations changes.
    active_config_changed(str)
        Emitted when the active configuration name changes.
    new_mods_detected(list[str])
        Emitted after collect(); filenames of newly moved mods (for highlighting).
    conflicts_detected(list)
        Emitted when collect() finds filename collisions.
        GUI must call resolve_conflict() for each item.
    status_changed(str)
        Short status text for display in the main window.
    error_occurred(str)
        User-facing error message; GUI shows a dialog.
    warning_occurred(str)
        User-facing warning message; GUI shows a warning dialog.
    """

    available_mods_changed = Signal(list)   # list[Mod]
    selected_mods_changed = Signal(list)    # list[Mod]
    config_names_changed = Signal(list)     # list[str]
    active_config_changed = Signal(str)
    new_mods_detected = Signal(list)        # list[str]
    conflicts_detected = Signal(list)       # list[MoveConflict]
    status_changed = Signal(str)
    error_occurred = Signal(str)
    warning_occurred = Signal(str)

    def __init__(
        self,
        settings_service: SettingsService,
        config_service: ConfigService,
        link_service: LinkService,
        collection_service: CollectionService,
        folder_move_service: FolderMoveService | None = None,
        export_service: ExportService | None = None,
        mod_rename_service: ModRenameService | None = None,
        configs_dir_factory: Callable[[Settings], Path] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings_svc = settings_service
        self._config_svc = config_service
        self._configs_dir_factory = configs_dir_factory
        self._link_svc = link_service
        self._collection_svc = collection_service
        self._folder_move_svc = folder_move_service or FolderMoveService()
        self._export_svc = export_service or ExportService()
        self._rename_svc = mod_rename_service or ModRenameService()

        self._settings: Settings | None = None
        self._available_mods: list[Mod] = []
        self._selected_mods: list[Mod] = []
        self._active_config_name: str = ""

    # ------------------------------------------------------------------
    # Read-only state (copies so callers can't mutate internals)
    # ------------------------------------------------------------------

    @property
    def settings(self) -> Settings | None:
        return self._settings

    @property
    def available_mods(self) -> list[Mod]:
        return list(self._available_mods)

    @property
    def selected_mods(self) -> list[Mod]:
        return list(self._selected_mods)

    @property
    def active_config_name(self) -> str:
        return self._active_config_name

    # ------------------------------------------------------------------
    # Initialisation (called once at startup)
    # ------------------------------------------------------------------

    def initialize(self, ask_for_path: Callable[[], str] | None = None) -> None:
        """Load settings, collect new mods, scan collection.

        The previously active configuration is deliberately *not*
        auto-selected here: showing a pre-filled config name with a full
        "selected" list right after startup falsely suggests those mods are
        already active, even though activate_config() has not run this
        session.
        """
        self._settings = self._settings_svc.load(ask_for_path)
        log.info("Settings loaded: source=%s  collection=%s  savegames=%s",
                 self._settings.source_mod_folder,
                 self._settings.mod_collection_folder,
                 self._settings.savegame_path)

        # If a factory was supplied (main.py use-case), realign the ConfigService
        # to the path that was actually resolved after ask_for_path ran.
        if self._configs_dir_factory is not None:
            configs_dir = self._configs_dir_factory(self._settings)
            log.info("ConfigService path updated to: %s", configs_dir)
            self._config_svc = ConfigService(configs_dir=configs_dir)

        self._collect_new_mods()
        self._load_mods_from_collection()

    # ------------------------------------------------------------------
    # Configuration management
    # ------------------------------------------------------------------

    def select_config(self, name: str) -> None:
        """Load config and split mods into available / selected."""
        # Return all currently selected mods to available first
        self._available_mods.extend(self._selected_mods)
        self._selected_mods = []

        if not self._config_svc.exists(name):
            self._set_active_config("")
            self._emit_mod_lists()
            return

        config = self._config_svc.load(name)
        selected_filenames = set(config.mod_filenames)

        remaining: list[Mod] = []
        moved: list[Mod] = []
        for mod in self._available_mods:
            (moved if mod.filename in selected_filenames else remaining).append(mod)

        self._available_mods = remaining
        self._selected_mods = moved
        bounced_maps = self._enforce_single_active_map()
        self._set_active_config(name)
        self._emit_mod_lists()
        self._warn_about_bounced_maps(bounced_maps)

        # Warn about mods that are in the config but no longer in the collection
        moved_filenames = {m.filename for m in moved}
        missing = [fn for fn in config.mod_filenames if fn not in moved_filenames]
        if missing:
            lines = "\n".join(f"  • {fn}" for fn in missing[:10])
            if len(missing) > 10:
                lines += f"\n  … und {len(missing) - 10} weitere"
            self.warning_occurred.emit(
                f"Folgende Mods sind nicht mehr in der Sammlung vorhanden:\n{lines}"
            )

    def save_config(self) -> None:
        """Persist the current selection under the active config name."""
        if not self._active_config_name:
            return
        config = Configuration(
            name=self._active_config_name,
            mod_filenames=[m.filename for m in self._selected_mods],
        )
        self._config_svc.save(config)
        self.status_changed.emit("Gespeichert")

    def reload(self) -> None:
        """Re-scan the collection and re-apply the active config."""
        self._load_mods_from_collection()
        if self._active_config_name:
            self.select_config(self._active_config_name)
        self.config_names_changed.emit(self._config_svc.list_names())
        self.status_changed.emit("Neu geladen")

    def activate_config(self) -> None:
        """Create symlinks in source_dir for the current selection."""
        if self._settings is None:
            return
        # Safety net: _selected_mods should never hold more than one map
        # (every mutation path enforces that below), but activation is
        # irreversible enough (symlinks replace whatever was there) that
        # it's worth refusing outright if that invariant is ever violated,
        # rather than silently symlinking every map in.
        maps = [m for m in self._selected_mods if m.is_map]
        if len(maps) > 1:
            names = ", ".join(f"'{m.title or m.filename}'" for m in maps)
            self.error_occurred.emit(
                f"Es sind mehrere Karten in der Auswahl ({names}). "
                "Es darf immer nur eine Karte gleichzeitig aktiviert werden."
            )
            return
        filenames = [m.filename for m in self._selected_mods]
        source = Path(self._settings.source_mod_folder)
        collection = Path(self._settings.mod_collection_folder)
        try:
            self._link_svc.activate(filenames, source, collection)
        except LinkError as exc:
            self.error_occurred.emit(str(exc))
            return
        if self._settings and self._active_config_name:
            self._settings.active_modpack = self._active_config_name
            self._settings_svc.save(self._settings)
        self.status_changed.emit(f"{self._active_config_name} aktiv")

    def create_config(self, name: str) -> None:
        """Create a new empty configuration and select it."""
        config = Configuration(name=name, mod_filenames=[])
        self._config_svc.save(config)
        self._set_active_config(name)
        self.config_names_changed.emit(self._config_svc.list_names())

    def delete_config(self, name: str) -> None:
        try:
            self._config_svc.delete(name)
        except ConfigNotFoundError as exc:
            self.error_occurred.emit(str(exc))
            return
        if self._active_config_name == name:
            self._set_active_config("")
        self.config_names_changed.emit(self._config_svc.list_names())
        self.status_changed.emit(f"Konfiguration '{name}' gelöscht")

    def copy_config(self, source_name: str, target_name: str) -> None:
        try:
            self._config_svc.copy(source_name, target_name)
        except (ConfigNotFoundError, ConfigAlreadyExistsError) as exc:
            self.error_occurred.emit(str(exc))
            return
        self.config_names_changed.emit(self._config_svc.list_names())
        self.status_changed.emit(f"'{source_name}' kopiert nach '{target_name}'")

    def rename_config(self, old_name: str, new_name: str) -> None:
        try:
            self._config_svc.rename(old_name, new_name)
        except (ConfigNotFoundError, ConfigAlreadyExistsError) as exc:
            self.error_occurred.emit(str(exc))
            return
        if self._active_config_name == old_name:
            self._set_active_config(new_name)
        self.config_names_changed.emit(self._config_svc.list_names())

    # ------------------------------------------------------------------
    # Mod list manipulation
    # ------------------------------------------------------------------

    def move_to_selected(self, mods: list[Mod]) -> None:
        to_move = set(id(m) for m in mods)
        self._available_mods = [m for m in self._available_mods if id(m) not in to_move]
        self._selected_mods.extend(mods)
        bounced = self._enforce_single_active_map()
        self._emit_mod_lists()
        self._warn_about_bounced_maps(bounced)

    def move_to_available(self, mods: list[Mod]) -> None:
        to_move = set(id(m) for m in mods)
        self._selected_mods = [m for m in self._selected_mods if id(m) not in to_move]
        self._available_mods.extend(mods)
        self._emit_mod_lists()

    def move_all_to_selected(self) -> None:
        self._selected_mods.extend(self._available_mods)
        self._available_mods = []
        bounced = self._enforce_single_active_map()
        self._emit_mod_lists()
        self._warn_about_bounced_maps(bounced)

    def move_all_to_available(self) -> None:
        self._available_mods.extend(self._selected_mods)
        self._selected_mods = []
        self._emit_mod_lists()

    # ------------------------------------------------------------------
    # Savegame import
    # ------------------------------------------------------------------

    def import_savegame(self, xml_path: Path) -> None:
        """Parse savegame XML, save as config, select it."""
        try:
            config = parse_savegame(xml_path)
        except SavegameParseError as exc:
            self.error_occurred.emit(str(exc))
            return
        self._config_svc.save(config)
        self.config_names_changed.emit(self._config_svc.list_names())
        self.select_config(config.name)
        self.status_changed.emit(f"Savegame '{config.name}' geladen")

    def import_all_savegames(self) -> None:
        """Import every savegame\\d+ folder as a config (first-start flow)."""
        import re as _re
        if self._settings is None:
            return
        savegame_base = Path(self._settings.savegame_path)
        if not savegame_base.is_dir():
            return
        imported = 0
        for d in sorted(savegame_base.iterdir()):
            if not (d.is_dir() and _re.fullmatch(r"savegame\d+", d.name)):
                continue
            xml_path = d / "careerSavegame.xml"
            if not xml_path.exists():
                continue
            try:
                config = parse_savegame(xml_path)
                self._config_svc.save(config)
                imported += 1
            except SavegameParseError as exc:
                log.warning("Skipping savegame %s: %s", d.name, exc)
        if imported:
            self.config_names_changed.emit(self._config_svc.list_names())
            self.status_changed.emit(f"{imported} Savegame(s) importiert")

    # ------------------------------------------------------------------
    # Export (new feature, no Java equivalent)
    # ------------------------------------------------------------------

    def export_selected_mods(self, target_path: Path) -> None:
        """Bundle every mod currently in the "selected" column into one ZIP
        at target_path, so the whole set can be shared as a single file.

        Operates on the current in-memory selection – it does not require
        the selection to match a saved configuration.
        """
        if self._settings is None:
            return
        if not self._selected_mods:
            self.warning_occurred.emit("Es sind keine Mods in der Auswahl zum Exportieren.")
            return

        collection = Path(self._settings.mod_collection_folder)
        filenames = [m.filename for m in self._selected_mods]
        try:
            result = self._export_svc.export(filenames, collection, target_path)
        except ExportError as exc:
            self.error_occurred.emit(str(exc))
            return

        if result.missing:
            lines = "\n".join(f"  • {fn}" for fn in result.missing)
            self.warning_occurred.emit(
                f"{len(result.missing)} Mod(s) wurden im Sammelordner nicht "
                f"gefunden und daher nicht mit exportiert:\n{lines}"
            )
        self.status_changed.emit(
            f"{len(result.exported)} Mod(s) exportiert nach {result.target_path.name}"
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def save_settings(self, settings: Settings) -> None:
        self._settings = settings
        self._settings_svc.save(settings)

    def move_collection_folder(self, old_dir: Path, new_dir: Path) -> list[str]:
        """Physically move mod files into a newly chosen collection folder.

        Called by the GUI, after user confirmation, when the collection
        path changes in Settings. Returns filenames that failed to move.
        """
        failed = self._folder_move_svc.move_collection_folder(old_dir, new_dir)
        if failed:
            log.warning("Konnte %d Mod(s) nicht in den neuen Sammelordner verschieben: %s",
                        len(failed), failed)
        return failed

    def move_source_folder(self, old_dir: Path, new_dir: Path, new_collection_dir: Path) -> list[str]:
        """Physically move mods/symlinks into a newly chosen source folder.

        Called by the GUI, after user confirmation, when the source path
        changes in Settings. Returns filenames that failed to move.
        """
        failed = self._folder_move_svc.move_source_folder(old_dir, new_dir, new_collection_dir)
        if failed:
            log.warning("Konnte %d Mod(s) nicht in den neuen Mod-Ordner verschieben: %s",
                        len(failed), failed)
        return failed

    # ------------------------------------------------------------------
    # Conflict resolution (called by GUI after conflicts_detected)
    # ------------------------------------------------------------------

    def resolve_conflict(self, conflict: MoveConflict, resolution: ConflictResolution) -> None:
        self._collection_svc.resolve_conflict(conflict, resolution)
        if resolution != ConflictResolution.SKIP:
            # Reload mods so the newly linked mod appears correctly
            self._load_mods_from_collection()

    # ------------------------------------------------------------------
    # Mod renaming (fixing a Mod.has_invalid_name filename)
    # ------------------------------------------------------------------

    def suggest_valid_mod_name(self, filename: str) -> str:
        """Best-effort corrected filename for the GUI to prefill; the user
        can still edit it before confirming."""
        return sanitize_mod_name(filename)

    def check_rename_conflict(self, mod: Mod, new_filename: str) -> MoveConflict | None:
        """Call before rename_mod(): non-None means new_filename is already
        taken and the GUI must ask the user to resolve it (same
        Überschreiben/Behalten/Überspringen prompt as a collect() conflict)."""
        if self._settings is None:
            return None
        collection = Path(self._settings.mod_collection_folder)
        return self._rename_svc.check_conflict(mod.filename, new_filename, collection)

    def rename_mod(
        self,
        mod: Mod,
        new_filename: str,
        resolution: ConflictResolution = ConflictResolution.OVERWRITE,
    ) -> None:
        """Fix mod's invalid filename (see Mod.has_invalid_name) in the
        collection folder, including the active symlink if it's currently
        selected+activated and every saved Configuration that references the
        old filename - so a saved pack doesn't silently lose the mod the
        next time it's loaded.

        resolution only matters when check_rename_conflict() found an
        existing file at new_filename: OVERWRITE replaces it with this mod,
        KEEP_EXISTING discards this mod as a duplicate of the existing one,
        SKIP (the default GUI escape hatch) does nothing at all.
        """
        if self._settings is None or resolution == ConflictResolution.SKIP:
            return
        collection = Path(self._settings.mod_collection_folder)
        source = Path(self._settings.source_mod_folder)
        old_filename = mod.filename
        was_selected = mod in self._selected_mods
        applied = self._rename_svc.rename(old_filename, new_filename, collection, source, resolution)

        self._remove_filename_from_configs(old_filename, replacement=new_filename)
        if applied:
            # Mutate *before* reloading: _load_mods_from_collection() matches
            # the freshly re-scanned mods back to _selected_mods by filename,
            # so without this the renamed mod would wrongly fall back to
            # "available" even though it was selected a moment ago.
            mod.filename = new_filename
            self.status_changed.emit(f"Mod umbenannt: {old_filename} → {new_filename}")
        else:
            self.status_changed.emit(
                f"'{old_filename}' verworfen – '{new_filename}' war bereits vorhanden"
            )
        self._load_mods_from_collection()

        if not applied and was_selected:
            # The invalid mod's file is gone (deduplicated away); carry the
            # selection over to the pre-existing mod it was matched against,
            # so the user doesn't lose their selection over a rename.
            for i, m in enumerate(self._available_mods):
                if m.filename == new_filename:
                    self._selected_mods.append(self._available_mods.pop(i))
                    self._emit_mod_lists()
                    break

    def delete_mod(self, mod: Mod) -> None:
        """Permanently delete mod's file from the collection folder (and its
        active symlink, if present). Also drops it from every saved
        Configuration that references it, so a saved pack doesn't keep
        pointing at a file that no longer exists."""
        if self._settings is None:
            return
        collection = Path(self._settings.mod_collection_folder)
        source = Path(self._settings.source_mod_folder)
        self._collection_svc.delete(mod.filename, collection, source)
        self._remove_filename_from_configs(mod.filename)
        self.status_changed.emit(f"Mod gelöscht: {mod.filename}")
        self._load_mods_from_collection()

    def _remove_filename_from_configs(self, filename: str, replacement: str | None = None) -> None:
        """Remove filename from every saved Configuration that references it,
        optionally replacing it with `replacement` instead of just dropping
        it (used by rename_mod(); delete_mod() just drops it). No-op for
        configs that don't mention it."""
        for name in self._config_svc.list_names():
            config = self._config_svc.load(name)
            if filename not in config.mod_filenames:
                continue
            filenames = [f for f in config.mod_filenames if f != filename]
            if replacement is not None and replacement not in filenames:
                filenames.append(replacement)
            self._config_svc.save(Configuration(name=name, mod_filenames=filenames))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_new_mods(self) -> None:
        if self._settings is None:
            return
        source = Path(self._settings.source_mod_folder)
        collection = Path(self._settings.mod_collection_folder)
        log.debug("Collecting new mods: source=%s  collection=%s", source, collection)
        if not source.exists():
            log.warning("Source mod folder does not exist: %s", source)
            return
        # Real (non-symlink) .zip files are exactly the ones collect() is
        # about to move+link – i.e. genuinely new this run. Must be captured
        # *before* collect() runs, since it turns them into symlinks.
        # Re-scanning source for symlinks *after* collect() (as done
        # previously) would also catch symlinks left over from an earlier
        # activate_config() call and wrongly flag already-active mods as new.
        # Mirrors Java moveMods(), which builds newMods from the same
        # pre-collect realFiles list.
        new_filenames = [
            p.name for p in source.iterdir()
            if p.suffix.lower() == ".zip" and p.is_file() and not p.is_symlink()
        ]
        conflicts = self._collection_svc.collect(source, collection)
        log.debug("New mods after collect: %s", new_filenames)
        if new_filenames:
            self.new_mods_detected.emit(new_filenames)
            self._warn_about_invalid_names(new_filenames)
        if conflicts:
            log.info("%d conflict(s) detected during collect", len(conflicts))
            self.conflicts_detected.emit(conflicts)

    def _load_mods_from_collection(self) -> None:
        if self._settings is None:
            return
        collection = Path(self._settings.mod_collection_folder)
        log.debug("Loading mods from collection: %s", collection)
        if not collection.exists():
            log.warning("Collection folder does not exist: %s", collection)
            self._available_mods = []
            self.available_mods_changed.emit([])
            return

        selected_filenames = {m.filename for m in self._selected_mods}
        mods: list[Mod] = []
        zip_paths = sorted(collection.glob("*.zip"))
        log.debug("ZIP files found in collection: %d", len(zip_paths))
        for zip_path in zip_paths:
            try:
                mods.append(parse_mod(zip_path))
            except ModParseError as exc:
                log.warning("Skipping unreadable mod ZIP %s: %s", zip_path.name, exc)

        log.info("Mods loaded from collection: %d total, %d selected, %d available",
                 len(mods),
                 sum(1 for m in mods if m.filename in selected_filenames),
                 sum(1 for m in mods if m.filename not in selected_filenames))

        # Preserve current selection split
        self._available_mods = [m for m in mods if m.filename not in selected_filenames]
        self._selected_mods = [m for m in mods if m.filename in selected_filenames]
        self._emit_mod_lists()

    def _enforce_single_active_map(self) -> list[Mod]:
        """At most one map mod (Mod.is_map) may be in "selected" at once -
        FS only loads one map per savegame, so having several active
        simultaneously doesn't make sense. New feature, no Java equivalent.

        Called after every mutation that can add mods to _selected_mods
        (move_to_selected, move_all_to_selected, select_config). Keeps the
        *last* map in list order - since every caller appends newly-added
        mods to the end of _selected_mods, that's the most recently added
        one, giving natural "picking a new map swaps out the old one"
        behaviour - and bounces any earlier map(s) back to "available".

        Returns the bounced maps (empty if nothing needed to change) so the
        caller can emit lists-changed *before* warning about it - matches
        the ordering select_config() already uses for its "missing mods"
        warning, so the GUI shows the resulting state before explaining it.
        """
        maps = [m for m in self._selected_mods if m.is_map]
        if len(maps) <= 1:
            return []

        bounced = maps[:-1]
        bounced_ids = {id(m) for m in bounced}
        self._selected_mods = [m for m in self._selected_mods if id(m) not in bounced_ids]
        self._available_mods.extend(bounced)
        return bounced

    def _warn_about_bounced_maps(self, bounced: list[Mod]) -> None:
        """Emit the warning for maps _enforce_single_active_map() had to
        bounce back to "available". No-op if the list is empty."""
        if not bounced:
            return
        keep = next((m for m in self._selected_mods if m.is_map), None)
        keep_label = f"'{keep.title or keep.filename}'" if keep else "die zuletzt gewählte Karte"
        bounced_names = ", ".join(f"'{m.title or m.filename}'" for m in bounced)
        self.warning_occurred.emit(
            "Es kann immer nur eine Karte gleichzeitig aktiv sein. "
            f"{keep_label} bleibt ausgewählt; "
            f"folgende Karte(n) wurden zurück nach 'Verfügbar' verschoben: {bounced_names}"
        )

    def _warn_about_invalid_names(self, filenames: list[str]) -> None:
        """Warn right away about newly collected mods whose filename FS itself
        will reject at load time with "Invalid mod name ...!" - catching this
        here, instead of leaving the user to find it in FS's log later, is the
        whole point: it's a recurring mistake (e.g. a browser adding "(1)" to
        a duplicate download)."""
        invalid = [fn for fn in filenames if not is_valid_mod_name(fn)]
        if not invalid:
            return
        lines = "\n".join(f"  • {fn}" for fn in invalid[:10])
        if len(invalid) > 10:
            lines += f"\n  … und {len(invalid) - 10} weitere"
        self.warning_occurred.emit(
            "Folgende neu hinzugefügte Mods haben einen ungültigen Dateinamen "
            "und werden vom Farming Simulator abgelehnt (\"Invalid mod name\"):\n"
            f"{lines}\n\n"
            "Erlaubt sind nur Buchstaben, Ziffern und Unterstrich (_); "
            "das erste Zeichen darf keine Ziffer sein. Bitte die Datei(en) "
            "entsprechend umbenennen."
        )

    def _set_active_config(self, name: str) -> None:
        self._active_config_name = name
        self.active_config_changed.emit(name)

    @staticmethod
    def _sort_key(mod: Mod) -> str:
        return (mod.title or mod.filename).casefold()

    def _emit_mod_lists(self) -> None:
        self._available_mods.sort(key=self._sort_key)
        self._selected_mods.sort(key=self._sort_key)
        self.available_mods_changed.emit(list(self._available_mods))
        self.selected_mods_changed.emit(list(self._selected_mods))
