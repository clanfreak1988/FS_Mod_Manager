import zipfile
from pathlib import Path

import pytest

from fsmodmanager.core.service.export_service import (
    ExportError,
    ExportResult,
    ExportService,
)


def _add_mod_zip(directory: Path, filename: str, content: bytes = b"dummy-payload") -> Path:
    p = directory / filename
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("modDesc.xml", content)
    return p


@pytest.fixture
def svc() -> ExportService:
    return ExportService()


@pytest.fixture
def collection(tmp_path: Path) -> Path:
    d = tmp_path / "collection"
    d.mkdir()
    return d


class TestExport:
    def test_bundles_all_mods_into_one_zip(self, svc: ExportService, collection: Path, tmp_path: Path) -> None:
        _add_mod_zip(collection, "FS25_ModA.zip", b"A")
        _add_mod_zip(collection, "FS25_ModB.zip", b"B")
        target = tmp_path / "export" / "bundle.zip"

        result = svc.export(["FS25_ModA.zip", "FS25_ModB.zip"], collection, target)

        assert isinstance(result, ExportResult)
        assert target.exists()
        assert sorted(result.exported) == ["FS25_ModA.zip", "FS25_ModB.zip"]
        assert result.missing == []

        with zipfile.ZipFile(target) as out:
            assert sorted(out.namelist()) == ["FS25_ModA.zip", "FS25_ModB.zip"]

    def test_entries_are_original_mod_zips_verbatim(
        self, svc: ExportService, collection: Path, tmp_path: Path
    ) -> None:
        """The outer archive must contain the *original* per-mod ZIP bytes as
        one entry each (not a merge of their contents), so the recipient can
        extract it straight into a mods folder."""
        src = _add_mod_zip(collection, "FS25_ModA.zip", b"payload-A")
        target = tmp_path / "bundle.zip"

        svc.export(["FS25_ModA.zip"], collection, target)

        with zipfile.ZipFile(target) as out:
            extracted = out.read("FS25_ModA.zip")
        assert extracted == src.read_bytes()
        # And that extracted bytes are themselves a valid, openable ZIP.
        import io
        with zipfile.ZipFile(io.BytesIO(extracted)) as inner:
            assert inner.read("modDesc.xml") == b"payload-A"

    def test_missing_mod_is_reported_not_fatal(
        self, svc: ExportService, collection: Path, tmp_path: Path
    ) -> None:
        _add_mod_zip(collection, "FS25_ModA.zip")
        target = tmp_path / "bundle.zip"

        result = svc.export(["FS25_ModA.zip", "FS25_Ghost.zip"], collection, target)

        assert result.exported == ["FS25_ModA.zip"]
        assert result.missing == ["FS25_Ghost.zip"]
        with zipfile.ZipFile(target) as out:
            assert out.namelist() == ["FS25_ModA.zip"]

    def test_empty_selection_raises(self, svc: ExportService, collection: Path, tmp_path: Path) -> None:
        with pytest.raises(ExportError):
            svc.export([], collection, tmp_path / "bundle.zip")

    def test_all_missing_raises_and_cleans_up(
        self, svc: ExportService, collection: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "bundle.zip"
        with pytest.raises(ExportError):
            svc.export(["FS25_Ghost.zip"], collection, target)
        assert not target.exists()

    def test_creates_missing_target_directory(
        self, svc: ExportService, collection: Path, tmp_path: Path
    ) -> None:
        _add_mod_zip(collection, "FS25_ModA.zip")
        target = tmp_path / "nested" / "dir" / "bundle.zip"

        svc.export(["FS25_ModA.zip"], collection, target)

        assert target.exists()

    def test_uses_stored_compression_for_outer_archive(
        self, svc: ExportService, collection: Path, tmp_path: Path
    ) -> None:
        """Inner mod ZIPs are already compressed; the outer container should
        not re-compress them."""
        _add_mod_zip(collection, "FS25_ModA.zip")
        target = tmp_path / "bundle.zip"

        svc.export(["FS25_ModA.zip"], collection, target)

        with zipfile.ZipFile(target) as out:
            info = out.getinfo("FS25_ModA.zip")
            assert info.compress_type == zipfile.ZIP_STORED
