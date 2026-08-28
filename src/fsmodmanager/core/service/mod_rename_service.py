import os
import shutil
from pathlib import Path

from fsmodmanager.core.service.collection_service import (
    ConflictResolution,
    MoveConflict,
    build_conflict,
)


class ModRenameService:
    """Fixes a mod's invalid FS filename in place inside the collection folder.

    FS itself rejects a mod ZIP whose filename doesn't match its naming rule
    (see Mod.has_invalid_name / core.model.mod.is_valid_mod_name). Renaming
    can collide with an existing file of the same corrected name - most
    commonly because the invalid name was a browser's "(1)" duplicate-
    download suffix on an otherwise identical mod - so the same
    overwrite/keep/skip choice as CollectionService.resolve_conflict() is
    offered for that case.
    """

    def check_conflict(
        self, old_filename: str, new_filename: str, collection_dir: Path
    ) -> MoveConflict | None:
        """Return a MoveConflict if new_filename is already taken, else None."""
        new_path = collection_dir / new_filename
        if not new_path.exists():
            return None
        return build_conflict(collection_dir / old_filename, new_path)

    def rename(
        self,
        old_filename: str,
        new_filename: str,
        collection_dir: Path,
        source_dir: Path,
        resolution: ConflictResolution = ConflictResolution.OVERWRITE,
    ) -> bool:
        """Rename the mod's file in the collection folder.

        Returns True if the mod now exists under new_filename (OVERWRITE, or
        a conflict-free rename); False if the invalid-named file was
        discarded instead (KEEP_EXISTING) or nothing changed at all (SKIP) -
        the caller uses this to decide whether to update its in-memory Mod
        entry and any saved Configurations.
        """
        old_path = collection_dir / old_filename
        new_path = collection_dir / new_filename

        if new_path.exists():
            if resolution == ConflictResolution.SKIP:
                return False
            if resolution == ConflictResolution.KEEP_EXISTING:
                old_path.unlink()
                # Mirrors CollectionService.resolve_conflict(): keeping the
                # existing file means discarding the invalid-named one - but
                # unlike there, we must NOT recreate a symlink under the
                # invalid name, since eliminating that name everywhere is the
                # whole point of the rename feature. If it was active, that
                # link would otherwise dangle, so just drop it.
                self._remove_symlink(old_filename, source_dir)
                return False
            new_path.unlink()  # OVERWRITE

        shutil.move(str(old_path), str(new_path))
        self._relink(old_filename, new_filename, collection_dir, source_dir)
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_symlink(filename: str, source_dir: Path) -> None:
        """Drop the active-mod symlink left dangling by discarding the file
        it pointed to (KEEP_EXISTING deleted the real file it targeted)."""
        link = source_dir / filename
        if link.is_symlink():
            link.unlink()

    @staticmethod
    def _relink(old_filename: str, new_filename: str, collection_dir: Path, source_dir: Path) -> None:
        """If the mod is currently active (a symlink named old_filename sits
        in source_dir), point a same-purpose symlink at the new name."""
        old_link = source_dir / old_filename
        if not old_link.is_symlink():
            return
        old_link.unlink()
        os.symlink(collection_dir / new_filename, source_dir / new_filename)
