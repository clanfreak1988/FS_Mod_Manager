import json
from pathlib import Path

from fsmodmanager.core.model.configuration import Configuration


class ConfigNotFoundError(Exception):
    """Raised when a requested configuration does not exist."""


class ConfigAlreadyExistsError(Exception):
    """Raised when a target configuration name is already taken."""


class ConfigService:
    """Manages named mod configurations on disk.

    Each configuration is stored as a plain JSON array of mod filenames
    in `configs_dir/<name>.json`, exactly matching the Java format
    (ModPacks / LS_sg_config/).  Existing Java config files can therefore
    be read without any migration step.

    Migration decision: no migration code needed – the file format is
    identical (JSON array of strings).
    """

    def __init__(self, configs_dir: Path) -> None:
        self._dir = configs_dir

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def list_names(self) -> list[str]:
        """Return all config names sorted case-insensitively."""
        if not self._dir.exists():
            return []
        return sorted(
            (p.stem for p in self._dir.glob("*.json")),
            key=str.casefold,
        )

    def load(self, name: str) -> Configuration:
        """Load a single configuration by name.

        Raises ConfigNotFoundError if the file does not exist.
        """
        path = self._path(name)
        if not path.exists():
            raise ConfigNotFoundError(f"Konfiguration '{name}' nicht gefunden")
        mod_filenames: list[str] = json.loads(path.read_text(encoding="utf-8"))
        return Configuration(name=name, mod_filenames=mod_filenames)

    def load_all(self) -> list[Configuration]:
        """Load every configuration file; returns empty list if directory missing."""
        return [self.load(name) for name in self.list_names()]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def save(self, config: Configuration) -> None:
        """Create or overwrite a configuration file."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(config.name).write_text(
            json.dumps(config.mod_filenames, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete(self, name: str) -> None:
        """Delete a configuration file.

        Raises ConfigNotFoundError if it does not exist.
        """
        path = self._path(name)
        if not path.exists():
            raise ConfigNotFoundError(f"Konfiguration '{name}' nicht gefunden")
        path.unlink()

    def copy(self, source_name: str, target_name: str) -> None:
        """Copy a configuration under a new name.

        Raises ConfigNotFoundError if source does not exist.
        Raises ConfigAlreadyExistsError if target already exists.
        """
        if not self.exists(source_name):
            raise ConfigNotFoundError(f"Konfiguration '{source_name}' nicht gefunden")
        if self.exists(target_name):
            raise ConfigAlreadyExistsError(
                f"Konfiguration '{target_name}' existiert bereits"
            )
        config = self.load(source_name)
        self.save(Configuration(name=target_name, mod_filenames=config.mod_filenames))

    def rename(self, old_name: str, new_name: str) -> None:
        """Rename a configuration (copy + delete original).

        Raises ConfigNotFoundError if source does not exist.
        Raises ConfigAlreadyExistsError if target already exists.
        """
        self.copy(old_name, new_name)
        self.delete(old_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.json"
