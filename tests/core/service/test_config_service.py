from pathlib import Path

import pytest

from fsmodmanager.core.model.configuration import Configuration
from fsmodmanager.core.service.config_service import (
    ConfigAlreadyExistsError,
    ConfigNotFoundError,
    ConfigService,
)


@pytest.fixture
def svc(tmp_path: Path) -> ConfigService:
    return ConfigService(configs_dir=tmp_path / "configs")


@pytest.fixture
def saved_config(svc: ConfigService) -> Configuration:
    config = Configuration(name="MeinHof", mod_filenames=["FS22_B.zip", "FS22_A.zip"])
    svc.save(config)
    return config


class TestSaveAndLoad:
    def test_save_creates_file(self, svc: ConfigService, tmp_path: Path) -> None:
        svc.save(Configuration(name="Test", mod_filenames=[]))
        assert (tmp_path / "configs" / "Test.json").exists()

    def test_load_roundtrip(self, svc: ConfigService, saved_config: Configuration) -> None:
        loaded = svc.load("MeinHof")
        assert loaded == saved_config

    def test_load_filenames_sorted(self, svc: ConfigService) -> None:
        svc.save(Configuration(name="X", mod_filenames=["FS22_Z.zip", "FS22_A.zip"]))
        assert svc.load("X").mod_filenames == ["FS22_A.zip", "FS22_Z.zip"]

    def test_save_overwrites(self, svc: ConfigService, saved_config: Configuration) -> None:
        updated = Configuration(name="MeinHof", mod_filenames=["FS22_New.zip"])
        svc.save(updated)
        assert svc.load("MeinHof").mod_filenames == ["FS22_New.zip"]

    def test_save_creates_parent_dir(self, tmp_path: Path) -> None:
        svc = ConfigService(configs_dir=tmp_path / "a" / "b" / "configs")
        svc.save(Configuration(name="X", mod_filenames=[]))
        assert svc.exists("X")

    def test_java_format_compatible(self, svc: ConfigService, tmp_path: Path) -> None:
        """A plain JSON array (Java format) is loaded correctly."""
        import json
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        (configs_dir / "JavaConfig.json").write_text(
            json.dumps(["FS22_ModA.zip", "FS22_ModB.zip"]), encoding="utf-8"
        )
        config = svc.load("JavaConfig")
        assert config.name == "JavaConfig"
        assert "FS22_ModA.zip" in config.mod_filenames


class TestLoadAll:
    def test_empty_when_dir_missing(self, svc: ConfigService) -> None:
        assert svc.load_all() == []

    def test_returns_all_configs(self, svc: ConfigService) -> None:
        svc.save(Configuration(name="Alpha", mod_filenames=[]))
        svc.save(Configuration(name="Beta", mod_filenames=[]))
        assert len(svc.load_all()) == 2

    def test_sorted_case_insensitive(self, svc: ConfigService) -> None:
        for name in ("zebra", "Alpha", "mitte"):
            svc.save(Configuration(name=name, mod_filenames=[]))
        names = [c.name for c in svc.load_all()]
        assert names == sorted(names, key=str.casefold)


class TestExists:
    def test_false_before_save(self, svc: ConfigService) -> None:
        assert svc.exists("X") is False

    def test_true_after_save(self, svc: ConfigService) -> None:
        svc.save(Configuration(name="X", mod_filenames=[]))
        assert svc.exists("X") is True

    def test_false_after_delete(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.delete("MeinHof")
        assert svc.exists("MeinHof") is False


class TestDelete:
    def test_delete_removes_file(self, svc: ConfigService, saved_config: Configuration, tmp_path: Path) -> None:
        svc.delete("MeinHof")
        assert not (tmp_path / "configs" / "MeinHof.json").exists()

    def test_delete_missing_raises(self, svc: ConfigService) -> None:
        with pytest.raises(ConfigNotFoundError):
            svc.delete("Nichtvorhanden")


class TestCopy:
    def test_copy_creates_target(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.copy("MeinHof", "MeinHofKopie")
        assert svc.exists("MeinHofKopie")

    def test_copy_preserves_mods(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.copy("MeinHof", "Kopie")
        assert svc.load("Kopie").mod_filenames == saved_config.mod_filenames

    def test_copy_keeps_source(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.copy("MeinHof", "Kopie")
        assert svc.exists("MeinHof")

    def test_copy_missing_source_raises(self, svc: ConfigService) -> None:
        with pytest.raises(ConfigNotFoundError):
            svc.copy("Nichtvorhanden", "Ziel")

    def test_copy_existing_target_raises(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.save(Configuration(name="Ziel", mod_filenames=[]))
        with pytest.raises(ConfigAlreadyExistsError):
            svc.copy("MeinHof", "Ziel")


class TestRename:
    def test_rename_creates_new(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.rename("MeinHof", "NeuerName")
        assert svc.exists("NeuerName")

    def test_rename_removes_old(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.rename("MeinHof", "NeuerName")
        assert not svc.exists("MeinHof")

    def test_rename_preserves_mods(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.rename("MeinHof", "NeuerName")
        assert svc.load("NeuerName").mod_filenames == saved_config.mod_filenames

    def test_rename_missing_raises(self, svc: ConfigService) -> None:
        with pytest.raises(ConfigNotFoundError):
            svc.rename("Nichtvorhanden", "Ziel")

    def test_rename_existing_target_raises(self, svc: ConfigService, saved_config: Configuration) -> None:
        svc.save(Configuration(name="Ziel", mod_filenames=[]))
        with pytest.raises(ConfigAlreadyExistsError):
            svc.rename("MeinHof", "Ziel")


class TestListNames:
    def test_empty_list_when_no_dir(self, svc: ConfigService) -> None:
        assert svc.list_names() == []

    def test_lists_all_names(self, svc: ConfigService) -> None:
        for name in ("A", "B", "C"):
            svc.save(Configuration(name=name, mod_filenames=[]))
        assert set(svc.list_names()) == {"A", "B", "C"}
