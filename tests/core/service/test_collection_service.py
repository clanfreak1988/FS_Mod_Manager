import zipfile
from pathlib import Path

import pytest

from fsmodmanager.core.service.collection_service import (
    CollectionService,
    ConflictResolution,
    MoveConflict,
)

_MOD_DESC = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<modDesc descVersion="72">
    <author>Tester</author>
    <version>{version}</version>
    <title><en>Test Mod</en></title>
    <iconFilename>icon.png</iconFilename>
</modDesc>"""


def _add_valid_mod_zip(directory: Path, filename: str, version: str) -> Path:
    p = directory / filename
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("modDesc.xml", _MOD_DESC.format(version=version))
    return p


@pytest.fixture
def svc() -> CollectionService:
    return CollectionService()


@pytest.fixture
def dirs(tmp_path: Path):
    source = tmp_path / "mods"
    collection = tmp_path / "collection"
    source.mkdir()
    collection.mkdir()
    return source, collection


def _add_mod(directory: Path, filename: str, content: bytes = b"data") -> Path:
    p = directory / filename
    p.write_bytes(content)
    return p


class TestCollectNormalCase:
    def test_file_moved_to_collection(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        svc.collect(source, collection)
        assert (collection / "FS22_ModA.zip").exists()

    def test_symlink_created_in_source(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        svc.collect(source, collection)
        assert (source / "FS22_ModA.zip").is_symlink()

    def test_symlink_points_to_collection(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        svc.collect(source, collection)
        assert (source / "FS22_ModA.zip").resolve() == (collection / "FS22_ModA.zip").resolve()

    def test_multiple_files_moved(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        for name in ("FS22_A.zip", "FS22_B.zip", "FS22_C.zip"):
            _add_mod(source, name)
        conflicts = svc.collect(source, collection)
        assert conflicts == []
        assert len(list(collection.iterdir())) == 3

    def test_no_conflicts_returned(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        assert svc.collect(source, collection) == []

    def test_collect_skipped_when_collection_dir_missing(self, svc: CollectionService, tmp_path: Path) -> None:
        """collect() must NOT create the collection directory – the user sets it up."""
        source = tmp_path / "mods"
        source.mkdir()
        collection = tmp_path / "new" / "collection"
        _add_mod(source, "FS22_ModA.zip")
        result = svc.collect(source, collection)
        assert result == []
        assert not collection.exists(), "collect() must not create the collection dir"
        # The original ZIP must still be in the source folder (not moved)
        assert (source / "FS22_ModA.zip").exists()

    def test_empty_source_returns_no_conflicts(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        assert svc.collect(source, collection) == []

    def test_nonexistent_source_returns_no_conflicts(self, svc: CollectionService, tmp_path: Path) -> None:
        assert svc.collect(tmp_path / "missing", tmp_path / "col") == []


class TestCollectIgnoresNonZip:
    def test_txt_file_ignored(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        (source / "readme.txt").write_text("hello")
        svc.collect(source, collection)
        assert not (collection / "readme.txt").exists()

    def test_symlinks_ignored(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        real = collection / "FS22_Existing.zip"
        real.write_bytes(b"x")
        import os
        os.symlink(real, source / "FS22_Existing.zip")
        conflicts = svc.collect(source, collection)
        assert conflicts == []


class TestConflict:
    def test_conflict_returned_when_file_exists(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip", b"new")
        _add_mod(collection, "FS22_ModA.zip", b"old")
        conflicts = svc.collect(source, collection)
        assert len(conflicts) == 1
        assert conflicts[0].filename == "FS22_ModA.zip"

    def test_conflict_has_source_and_target_paths(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        _add_mod(collection, "FS22_ModA.zip")
        c = svc.collect(source, collection)[0]
        assert c.source_path == source / "FS22_ModA.zip"
        assert c.target_path == collection / "FS22_ModA.zip"

    def test_conflict_has_size_info(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip", b"new_content_12bytes")
        _add_mod(collection, "FS22_ModA.zip", b"old")
        c = svc.collect(source, collection)[0]
        assert c.source_size == len(b"new_content_12bytes")
        assert c.target_size == len(b"old")

    def test_conflict_has_modified_dates(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip")
        _add_mod(collection, "FS22_ModA.zip")
        c = svc.collect(source, collection)[0]
        assert c.source_modified is not None
        assert c.target_modified is not None

    def test_conflicting_file_not_moved(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip", b"new")
        _add_mod(collection, "FS22_ModA.zip", b"old")
        svc.collect(source, collection)
        # source file must still be a real file, not a symlink
        assert (source / "FS22_ModA.zip").exists()
        assert not (source / "FS22_ModA.zip").is_symlink()

    def test_conflict_has_version_info(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_valid_mod_zip(source, "FS22_ModA.zip", "2.0.0.0")
        _add_valid_mod_zip(collection, "FS22_ModA.zip", "1.0.0.0")
        c = svc.collect(source, collection)[0]
        assert c.source_version == "2.0.0.0"
        assert c.target_version == "1.0.0.0"

    def test_conflict_version_empty_when_unparseable(self, svc: CollectionService, dirs) -> None:
        """A non-ZIP or otherwise corrupt file must not blow up conflict building."""
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip", b"not a real zip")
        _add_mod(collection, "FS22_ModA.zip", b"also not a real zip")
        c = svc.collect(source, collection)[0]
        assert c.source_version == ""
        assert c.target_version == ""


class TestResolveConflict:
    def _make_conflict(self, dirs) -> tuple[MoveConflict, Path, Path]:
        source, collection = dirs
        _add_mod(source, "FS22_ModA.zip", b"new")
        _add_mod(collection, "FS22_ModA.zip", b"old")
        svc = CollectionService()
        conflict = svc.collect(source, collection)[0]
        return conflict, source, collection

    def test_overwrite_replaces_target(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.OVERWRITE)
        assert (collection / "FS22_ModA.zip").read_bytes() == b"new"

    def test_overwrite_creates_symlink(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.OVERWRITE)
        assert (source / "FS22_ModA.zip").is_symlink()

    def test_keep_existing_removes_source(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.KEEP_EXISTING)
        assert not (source / "FS22_ModA.zip").is_file() or (source / "FS22_ModA.zip").is_symlink()

    def test_keep_existing_creates_symlink(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.KEEP_EXISTING)
        assert (source / "FS22_ModA.zip").is_symlink()

    def test_keep_existing_preserves_collection_file(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.KEEP_EXISTING)
        assert (collection / "FS22_ModA.zip").read_bytes() == b"old"

    def test_skip_leaves_source_unchanged(self, dirs) -> None:
        conflict, source, collection = self._make_conflict(dirs)
        CollectionService().resolve_conflict(conflict, ConflictResolution.SKIP)
        assert (source / "FS22_ModA.zip").read_bytes() == b"new"
        assert not (source / "FS22_ModA.zip").is_symlink()


class TestDelete:
    def test_removes_file_from_collection(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(collection, "FS22_ModA.zip")
        svc.delete("FS22_ModA.zip", collection, source)
        assert not (collection / "FS22_ModA.zip").exists()

    def test_removes_active_symlink(self, svc: CollectionService, dirs) -> None:
        import os
        source, collection = dirs
        target = _add_mod(collection, "FS22_ModA.zip")
        os.symlink(target, source / "FS22_ModA.zip")
        svc.delete("FS22_ModA.zip", collection, source)
        assert not (source / "FS22_ModA.zip").exists()

    def test_noop_when_neither_present(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        svc.delete("FS22_NonExistent.zip", collection, source)  # must not raise

    def test_leaves_other_mods_untouched(self, svc: CollectionService, dirs) -> None:
        source, collection = dirs
        _add_mod(collection, "FS22_ModA.zip")
        _add_mod(collection, "FS22_ModB.zip")
        svc.delete("FS22_ModA.zip", collection, source)
        assert (collection / "FS22_ModB.zip").exists()
