import errno
import os
from pathlib import Path


class LinkError(Exception):
    """User-facing error from the link service.

    The message is in plain German and suitable for direct display in the GUI
    – no stacktrace, no internal details.
    """


class LinkService:
    """Creates and removes symbolic links when a configuration is activated.

    Mirrors Java Main.createLinks() / Files.createSymbolicLink():
    1. Remove all existing symlinks in source_dir (= FS mods folder).
    2. Create new symlinks: source_dir/<filename> → collection_dir/<filename>

    Windows note: symlinks require either the Developer Mode (Settings →
    For Developers → Developer Mode) or elevated admin rights.
    The minimum supported Windows version is Windows 11.
    """

    def activate(
        self,
        mod_filenames: list[str],
        source_dir: Path,
        collection_dir: Path,
    ) -> None:
        """Activate a configuration by replacing symlinks in source_dir.

        Steps (matching Java):
          1. Delete every symlink in source_dir.
          2. Create a symlink for each filename in mod_filenames pointing into
             collection_dir.

        Raises LinkError with a user-friendly message on any OS-level failure.
        """
        self.deactivate(source_dir)

        for filename in mod_filenames:
            link = source_dir / filename
            target = collection_dir / filename
            try:
                os.symlink(target, link)
            except PermissionError as exc:
                raise LinkError(
                    f"Symbolischer Link für '{filename}' konnte nicht erstellt werden: "
                    "Fehlende Berechtigung.\n\n"
                    "Unter Windows wird der Developer Mode benötigt:\n"
                    "Einstellungen → System → Für Entwickler → Developer Mode aktivieren.\n"
                    "Alternativ das Programm als Administrator starten."
                ) from exc
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    raise LinkError(
                        f"Symbolischer Link für '{filename}' konnte nicht erstellt werden: "
                        "Quelle und Ziel liegen auf unterschiedlichen Laufwerken.\n"
                        f"Mod-Ordner: {source_dir}\n"
                        f"Sammelordner: {collection_dir}"
                    ) from exc
                raise LinkError(
                    f"Symbolischer Link für '{filename}' konnte nicht erstellt werden: "
                    f"{exc.strerror} (errno {exc.errno})"
                ) from exc

    def deactivate(self, source_dir: Path) -> None:
        """Remove all symlinks from source_dir.

        Non-symlink files (real mod ZIPs) are never touched.
        Raises LinkError if source_dir cannot be read.
        """
        if not source_dir.exists():
            return
        try:
            for entry in source_dir.iterdir():
                if entry.is_symlink():
                    entry.unlink()
        except OSError as exc:
            raise LinkError(
                f"Konnte Mod-Ordner '{source_dir}' nicht einlesen: {exc.strerror}"
            ) from exc
