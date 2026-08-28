import os
import shutil
from pathlib import Path


class FolderMoveService:
    """Relocates mod folders when their Settings path changes.

    Mirrors Java Main.changeModFolders(): when the user points Settings at a
    new source/collection folder, the existing content must be physically
    moved there too, otherwise it's silently abandoned at the old path.
    """

    def move_collection_folder(self, old_dir: Path, new_dir: Path) -> list[str]:
        """Move every entry from old_dir into new_dir.

        Returns the filenames that could not be moved (logged by the caller);
        one failure does not abort the rest, matching Java's per-file
        try/catch in changeModFolders().
        """
        if old_dir == new_dir or not old_dir.is_dir():
            return []
        new_dir.mkdir(parents=True, exist_ok=True)
        failed: list[str] = []
        for entry in old_dir.iterdir():
            try:
                shutil.move(str(entry), str(new_dir / entry.name))
            except OSError:
                failed.append(entry.name)
        return failed

    def move_source_folder(
        self, old_dir: Path, new_dir: Path, new_collection_dir: Path
    ) -> list[str]:
        """Move every entry from old_dir into new_dir.

        Symlinks are recreated pointing into new_collection_dir (their real
        target moves there too via move_collection_folder); real files are
        moved directly. Returns the filenames that could not be moved.
        """
        if old_dir == new_dir or not old_dir.is_dir():
            return []
        new_dir.mkdir(parents=True, exist_ok=True)
        failed: list[str] = []
        for entry in old_dir.iterdir():
            target = new_dir / entry.name
            try:
                if entry.is_symlink():
                    os.symlink(new_collection_dir / entry.name, target)
                    entry.unlink()
                else:
                    shutil.move(str(entry), str(target))
            except OSError:
                failed.append(entry.name)
        return failed
