import errno
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fsmodmanager.core.service.link_service import LinkError, LinkService


@pytest.fixture
def svc() -> LinkService:
    return LinkService()


@pytest.fixture
def dirs(tmp_path: Path):
    source = tmp_path / "mods"
    collection = tmp_path / "collection"
    source.mkdir()
    collection.mkdir()
    return source, collection


@pytest.fixture
def populated(dirs):
    """collection dir pre-filled with two mod ZIPs."""
    source, collection = dirs
    (collection / "FS25_ModA.zip").write_bytes(b"modA")
    (collection / "FS25_ModB.zip").write_bytes(b"modB")
    return source, collection


class TestActivate:
    def test_creates_symlinks(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip", "FS25_ModB.zip"], source, collection)
        assert (source / "FS25_ModA.zip").is_symlink()
        assert (source / "FS25_ModB.zip").is_symlink()

    def test_symlinks_point_to_collection(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip"], source, collection)
        assert (source / "FS25_ModA.zip").resolve() == (collection / "FS25_ModA.zip").resolve()

    def test_replaces_old_symlinks(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip", "FS25_ModB.zip"], source, collection)
        # Now activate with only ModA – ModB link must be gone
        svc.activate(["FS25_ModA.zip"], source, collection)
        assert (source / "FS25_ModA.zip").is_symlink()
        assert not (source / "FS25_ModB.zip").exists()

    def test_real_files_in_source_not_touched(self, svc: LinkService, populated) -> None:
        source, collection = populated
        real_file = source / "FS25_RealMod.zip"
        real_file.write_bytes(b"real")
        svc.activate(["FS25_ModA.zip"], source, collection)
        assert real_file.exists()
        assert not real_file.is_symlink()

    def test_empty_config_removes_all_links(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip"], source, collection)
        svc.activate([], source, collection)
        assert not any(source.iterdir())

    def test_activate_twice_idempotent(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip"], source, collection)
        svc.activate(["FS25_ModA.zip"], source, collection)
        links = [e for e in source.iterdir() if e.is_symlink()]
        assert len(links) == 1


class TestDeactivate:
    def test_removes_all_symlinks(self, svc: LinkService, populated) -> None:
        source, collection = populated
        svc.activate(["FS25_ModA.zip", "FS25_ModB.zip"], source, collection)
        svc.deactivate(source)
        assert not any(e.is_symlink() for e in source.iterdir())

    def test_keeps_real_files(self, svc: LinkService, dirs) -> None:
        source, _ = dirs
        real = source / "FS25_Real.zip"
        real.write_bytes(b"x")
        svc.deactivate(source)
        assert real.exists()

    def test_nonexistent_dir_does_not_raise(self, svc: LinkService, tmp_path: Path) -> None:
        svc.deactivate(tmp_path / "does_not_exist")  # should not raise


class TestErrorHandling:
    def test_permission_error_raises_link_error(self, svc: LinkService, populated) -> None:
        source, collection = populated
        with patch("os.symlink", side_effect=PermissionError(errno.EPERM, "Not permitted")):
            with pytest.raises(LinkError) as exc_info:
                svc.activate(["FS25_ModA.zip"], source, collection)
        assert "Developer Mode" in str(exc_info.value)

    def test_cross_device_error_raises_link_error(self, svc: LinkService, populated) -> None:
        source, collection = populated
        cross_device = OSError(errno.EXDEV, "Cross-device link")
        with patch("os.symlink", side_effect=cross_device):
            with pytest.raises(LinkError) as exc_info:
                svc.activate(["FS25_ModA.zip"], source, collection)
        assert "unterschiedlichen Laufwerken" in str(exc_info.value)

    def test_generic_os_error_raises_link_error(self, svc: LinkService, populated) -> None:
        source, collection = populated
        with patch("os.symlink", side_effect=OSError(errno.EIO, "Input/output error")):
            with pytest.raises(LinkError):
                svc.activate(["FS25_ModA.zip"], source, collection)

    def test_link_error_message_contains_filename(self, svc: LinkService, populated) -> None:
        source, collection = populated
        with patch("os.symlink", side_effect=PermissionError(errno.EPERM, "x")):
            with pytest.raises(LinkError) as exc_info:
                svc.activate(["FS25_SpecialMod.zip"], source, collection)
        assert "FS25_SpecialMod.zip" in str(exc_info.value)
