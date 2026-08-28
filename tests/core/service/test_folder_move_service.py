import os
from pathlib import Path

import pytest

from fsmodmanager.core.service.folder_move_service import FolderMoveService


@pytest.fixture
def svc() -> FolderMoveService:
    return FolderMoveService()


class TestMoveCollectionFolder:
    def test_moves_all_files(self, svc: FolderMoveService, tmp_path: Path) -> None:
        old_dir = tmp_path / "old_collection"
        new_dir = tmp_path / "new_collection"
        old_dir.mkdir()
        (old_dir / "FS25_ModA.zip").write_bytes(b"modA")
        (old_dir / "FS25_ModB.zip").write_bytes(b"modB")

        failed = svc.move_collection_folder(old_dir, new_dir)

        assert failed == []
        assert (new_dir / "FS25_ModA.zip").read_bytes() == b"modA"
        assert (new_dir / "FS25_ModB.zip").read_bytes() == b"modB"
        assert not (old_dir / "FS25_ModA.zip").exists()

    def test_creates_new_dir_if_missing(self, svc: FolderMoveService, tmp_path: Path) -> None:
        old_dir = tmp_path / "old_collection"
        new_dir = tmp_path / "nested" / "new_collection"
        old_dir.mkdir()
        (old_dir / "FS25_ModA.zip").write_bytes(b"modA")

        svc.move_collection_folder(old_dir, new_dir)

        assert new_dir.is_dir()
        assert (new_dir / "FS25_ModA.zip").exists()

    def test_noop_when_paths_identical(self, svc: FolderMoveService, tmp_path: Path) -> None:
        same_dir = tmp_path / "collection"
        same_dir.mkdir()
        (same_dir / "FS25_ModA.zip").write_bytes(b"modA")

        failed = svc.move_collection_folder(same_dir, same_dir)

        assert failed == []
        assert (same_dir / "FS25_ModA.zip").exists()

    def test_noop_when_old_dir_missing(self, svc: FolderMoveService, tmp_path: Path) -> None:
        old_dir = tmp_path / "does_not_exist"
        new_dir = tmp_path / "new_collection"

        failed = svc.move_collection_folder(old_dir, new_dir)

        assert failed == []
        assert not new_dir.exists()

    def test_continues_after_one_failure(self, svc: FolderMoveService, tmp_path: Path, monkeypatch) -> None:
        old_dir = tmp_path / "old_collection"
        new_dir = tmp_path / "new_collection"
        old_dir.mkdir()
        (old_dir / "FS25_ModA.zip").write_bytes(b"modA")
        (old_dir / "FS25_ModB.zip").write_bytes(b"modB")

        import shutil
        real_move = shutil.move

        def flaky_move(src, dst):
            if "FS25_ModA" in str(src):
                raise OSError("boom")
            return real_move(src, dst)

        monkeypatch.setattr(shutil, "move", flaky_move)

        failed = svc.move_collection_folder(old_dir, new_dir)

        assert failed == ["FS25_ModA.zip"]
        assert (new_dir / "FS25_ModB.zip").exists()


class TestMoveSourceFolder:
    def test_moves_real_file_directly(self, svc: FolderMoveService, tmp_path: Path) -> None:
        old_dir = tmp_path / "old_source"
        new_dir = tmp_path / "new_source"
        collection_dir = tmp_path / "collection"
        old_dir.mkdir()
        (old_dir / "FS25_ModA.zip").write_bytes(b"modA")

        failed = svc.move_source_folder(old_dir, new_dir, collection_dir)

        assert failed == []
        assert (new_dir / "FS25_ModA.zip").read_bytes() == b"modA"

    def test_relinks_symlink_to_new_collection(self, svc: FolderMoveService, tmp_path: Path) -> None:
        old_dir = tmp_path / "old_source"
        new_dir = tmp_path / "new_source"
        old_collection = tmp_path / "old_collection"
        new_collection = tmp_path / "new_collection"
        old_dir.mkdir()
        old_collection.mkdir()
        new_collection.mkdir()
        (old_collection / "FS25_ModA.zip").write_bytes(b"modA")
        os.symlink(old_collection / "FS25_ModA.zip", old_dir / "FS25_ModA.zip")

        failed = svc.move_source_folder(old_dir, new_dir, new_collection)

        assert failed == []
        link = new_dir / "FS25_ModA.zip"
        assert link.is_symlink()
        assert os.readlink(link) == str(new_collection / "FS25_ModA.zip")
        assert not (old_dir / "FS25_ModA.zip").exists()

    def test_noop_when_paths_identical(self, svc: FolderMoveService, tmp_path: Path) -> None:
        same_dir = tmp_path / "source"
        collection_dir = tmp_path / "collection"
        same_dir.mkdir()
        (same_dir / "FS25_ModA.zip").write_bytes(b"modA")

        failed = svc.move_source_folder(same_dir, same_dir, collection_dir)

        assert failed == []
        assert (same_dir / "FS25_ModA.zip").exists()
