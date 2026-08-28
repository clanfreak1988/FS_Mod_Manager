import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from fsmodmanager.core.parser.mod_parser import ModParseError, parse_mod


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MoveConflict:
    """Describes a filename collision when collecting mods.

    Returned by CollectionService.collect() for files that already exist in
    the collection folder.  The GUI reads these fields to build a prompt
    (filename, dates, sizes, and mod versions of both files) and then calls
    resolve_conflict().

    Extends the information shown in Java Main.existingFile() (which only
    compared filename/date/size) with each side's modDesc.xml version, since
    that's the detail a user actually needs to judge which file to keep.
    version is "" when modDesc.xml can't be parsed (corrupt ZIP, etc.).
    """
    filename: str
    source_path: Path
    source_size: int
    source_modified: datetime
    source_version: str
    target_path: Path
    target_size: int
    target_modified: datetime
    target_version: str


class ConflictResolution(Enum):
    """User decision for a MoveConflict.

    OVERWRITE    – replace the existing collection file with the new one;
                   create a symlink from source to the new target.
    KEEP_EXISTING – discard the new file; create a symlink to the existing one.
    SKIP         – do nothing; leave the new file as a real file in source_dir.
    """
    OVERWRITE = auto()
    KEEP_EXISTING = auto()
    SKIP = auto()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CollectionService:
    """Moves newly added mod ZIPs from the FS mods folder into the collection folder.

    Workflow (matching Java Main.moveMods()):
    1. Call collect() – non-conflicting files are moved and symlinked immediately;
       a list of MoveConflict objects is returned for files that collide.
    2. For each conflict the GUI shows a dialog and calls resolve_conflict().
    """

    def collect(
        self,
        source_dir: Path,
        collection_dir: Path,
    ) -> list[MoveConflict]:
        """Move conflict-free mod ZIPs and return conflicts for the GUI to resolve.

        Only real (non-symlink) .zip files are considered.
        Directories and files with other extensions are ignored.
        """
        if not collection_dir.exists():
            return []
        conflicts: list[MoveConflict] = []

        for src in self._real_zips(source_dir):
            dst = collection_dir / src.name
            if dst.exists():
                conflicts.append(build_conflict(src, dst))
            else:
                _move_and_link(src, dst)

        return conflicts

    def resolve_conflict(
        self,
        conflict: MoveConflict,
        resolution: ConflictResolution,
    ) -> None:
        """Apply the user's decision for a single file conflict."""
        src = conflict.source_path
        dst = conflict.target_path

        if resolution == ConflictResolution.OVERWRITE:
            shutil.move(str(src), str(dst))
            _create_symlink(src, dst)

        elif resolution == ConflictResolution.KEEP_EXISTING:
            src.unlink()
            _create_symlink(src, dst)

        elif resolution == ConflictResolution.SKIP:
            pass  # leave the real file untouched

    def delete(self, filename: str, collection_dir: Path, source_dir: Path) -> None:
        """Permanently delete a mod: its real file in collection_dir, plus its
        active symlink in source_dir if it's currently selected+activated.
        Silently does nothing for whichever of the two isn't present."""
        path = collection_dir / filename
        if path.exists():
            path.unlink()
        link = source_dir / filename
        if link.is_symlink():
            link.unlink()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _real_zips(directory: Path) -> list[Path]:
        """Return non-symlink .zip files directly inside directory."""
        if not directory.exists():
            return []
        return [
            p for p in directory.iterdir()
            if p.suffix.lower() == ".zip"
            and p.is_file()
            and not p.is_symlink()
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_conflict(src: Path, dst: Path) -> MoveConflict:
    src_stat = src.stat()
    dst_stat = dst.stat()
    return MoveConflict(
        filename=src.name,
        source_path=src,
        source_size=src_stat.st_size,
        source_modified=datetime.fromtimestamp(src_stat.st_mtime),
        source_version=_read_version(src),
        target_path=dst,
        target_size=dst_stat.st_size,
        target_modified=datetime.fromtimestamp(dst_stat.st_mtime),
        target_version=_read_version(dst),
    )


def _read_version(zip_path: Path) -> str:
    """Return the mod's modDesc.xml version, or "" if it can't be parsed."""
    try:
        return parse_mod(zip_path).version
    except ModParseError:
        return ""


def _move_and_link(src: Path, dst: Path) -> None:
    shutil.move(str(src), str(dst))
    _create_symlink(src, dst)


def _create_symlink(link_path: Path, target_path: Path) -> None:
    os.symlink(target_path, link_path)
