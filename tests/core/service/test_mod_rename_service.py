import os
from pathlib import Path

import pytest

from fsmodmanager.core.service.collection_service import ConflictResolution, MoveConflict
from fsmodmanager.core.service.mod_rename_service import ModRenameService


@pytest.fixture
def svc() -> ModRenameService:
    return ModRenameService()


@pytest.fixture
def dirs(tmp_path: Path):
    source = tmp_path / "mods"
    collection = tmp_path / "collection"
    source.mkdir()
    collection.mkdir()
    return source, collection


class TestCheckConflict:
    def test_no_conflict_when_new_name_free(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"data")
        assert svc.check_conflict("Bad Name (1).zip", "GoodName.zip", collection) is None

    def test_conflict_when_new_name_taken(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"new")
        (collection / "GoodName.zip").write_bytes(b"existing")
        conflict = svc.check_conflict("Bad Name (1).zip", "GoodName.zip", collection)
        assert isinstance(conflict, MoveConflict)
        assert conflict.filename == "Bad Name (1).zip"


class TestRenameNoConflict:
    def test_file_renamed_in_collection(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"data")

        applied = svc.rename("Bad Name (1).zip", "GoodName.zip", collection, source)

        assert applied is True
        assert not (collection / "Bad Name (1).zip").exists()
        assert (collection / "GoodName.zip").read_bytes() == b"data"

    def test_active_symlink_relinked_to_new_name(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        target = collection / "Bad Name (1).zip"
        target.write_bytes(b"data")
        os.symlink(target, source / "Bad Name (1).zip")

        svc.rename("Bad Name (1).zip", "GoodName.zip", collection, source)

        assert not (source / "Bad Name (1).zip").exists()
        new_link = source / "GoodName.zip"
        assert new_link.is_symlink()
        assert os.readlink(new_link) == str(collection / "GoodName.zip")

    def test_no_symlink_created_when_mod_not_active(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"data")

        svc.rename("Bad Name (1).zip", "GoodName.zip", collection, source)

        assert not (source / "GoodName.zip").exists()


class TestRenameWithConflictOverwrite:
    def test_existing_file_replaced(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"new-content")
        (collection / "GoodName.zip").write_bytes(b"old-content")

        applied = svc.rename(
            "Bad Name (1).zip", "GoodName.zip", collection, source,
            resolution=ConflictResolution.OVERWRITE,
        )

        assert applied is True
        assert not (collection / "Bad Name (1).zip").exists()
        assert (collection / "GoodName.zip").read_bytes() == b"new-content"


class TestRenameWithConflictKeepExisting:
    def test_invalid_file_discarded_existing_kept(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"duplicate")
        (collection / "GoodName.zip").write_bytes(b"original")

        applied = svc.rename(
            "Bad Name (1).zip", "GoodName.zip", collection, source,
            resolution=ConflictResolution.KEEP_EXISTING,
        )

        assert applied is False
        assert not (collection / "Bad Name (1).zip").exists()
        assert (collection / "GoodName.zip").read_bytes() == b"original"

    def test_dangling_active_symlink_removed(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        invalid_target = collection / "Bad Name (1).zip"
        invalid_target.write_bytes(b"duplicate")
        (collection / "GoodName.zip").write_bytes(b"original")
        os.symlink(invalid_target, source / "Bad Name (1).zip")

        svc.rename(
            "Bad Name (1).zip", "GoodName.zip", collection, source,
            resolution=ConflictResolution.KEEP_EXISTING,
        )

        assert not (source / "Bad Name (1).zip").exists()
        assert not (source / "GoodName.zip").exists()


class TestRenameWithConflictSkip:
    def test_nothing_changes(self, svc: ModRenameService, dirs) -> None:
        source, collection = dirs
        (collection / "Bad Name (1).zip").write_bytes(b"data")
        (collection / "GoodName.zip").write_bytes(b"other")

        applied = svc.rename(
            "Bad Name (1).zip", "GoodName.zip", collection, source,
            resolution=ConflictResolution.SKIP,
        )

        assert applied is False
        assert (collection / "Bad Name (1).zip").read_bytes() == b"data"
        assert (collection / "GoodName.zip").read_bytes() == b"other"
