"""ExportService – bundles mod ZIPs into a single archive for sharing.

New feature, no Java equivalent: lets the user export every mod currently in
the "selected" column into one combined ZIP file, so the whole set can be
shared as a single download. Each mod's own ZIP file (as found in the
collection folder) is stored as-is under its original filename inside the
output archive – not merged/flattened, since two mods' internal file trees
(each with their own modDesc.xml etc.) would otherwise collide. The
recipient can therefore extract the result straight into their own mods
folder and get back the original per-mod ZIPs.

The output archive itself is written uncompressed (ZIP_STORED): the mod
ZIPs inside are already compressed, so re-compressing their bytes wastes
time for essentially no size reduction (and can even grow slightly).
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


class ExportError(Exception):
    """User-facing error from the export service.

    The message is in plain German and suitable for direct display in the
    GUI – no stacktrace, no internal details.
    """


@dataclass(frozen=True)
class ExportResult:
    """Outcome of a successful export() call."""
    target_path: Path
    exported: list[str]   # filenames actually written into the archive
    missing: list[str]    # filenames that were requested but not found


class ExportService:
    """Bundles mod ZIPs from the collection folder into one shareable archive."""

    def export(
        self,
        mod_filenames: list[str],
        collection_dir: Path,
        target_path: Path,
    ) -> ExportResult:
        """Write a single ZIP at target_path containing each of mod_filenames'
        source ZIP (read from collection_dir), stored under its original
        filename.

        Mods whose source ZIP can no longer be found in collection_dir are
        skipped (reported via ExportResult.missing) rather than aborting the
        whole export – one stale entry in the selection shouldn't block
        exporting everything else.

        Raises:
            ExportError: if mod_filenames is empty, target_path can't be
                written (permissions, disk full, …), or none of the
                requested mods could be found.
        """
        if not mod_filenames:
            raise ExportError("Keine Mods zum Exportieren ausgewählt.")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        exported: list[str] = []
        missing: list[str] = []

        try:
            with zipfile.ZipFile(target_path, "w", zipfile.ZIP_STORED) as out:
                for filename in mod_filenames:
                    src = collection_dir / filename
                    if not src.is_file():
                        missing.append(filename)
                        continue
                    out.write(src, arcname=filename)
                    exported.append(filename)
        except OSError as exc:
            raise ExportError(
                f"Export nach '{target_path}' fehlgeschlagen: "
                f"{exc.strerror or exc}"
            ) from exc

        if not exported:
            target_path.unlink(missing_ok=True)
            raise ExportError(
                "Keine der ausgewählten Mods wurde im Sammelordner gefunden."
            )

        return ExportResult(target_path=target_path, exported=exported, missing=missing)
