import os
import sys
from collections.abc import Callable
from pathlib import Path

from fsmodmanager.core.app_paths import DATA_DIR
from fsmodmanager.core.model.settings import Settings

_SETTINGS_FILE = "settings.json"

# Relative to the user's Documents folder – matches the Java default paths.
_FS22_SUBPATH = Path("My Games") / "FarmingSimulator2022"


def _windows_documents_dir() -> Path | None:
    """Resolve the real Windows "Documents" folder via the registry.

    ``%USERPROFILE%\\Documents`` is only the *default* location. It is
    frequently wrong once the folder has been redirected – most commonly by
    OneDrive's "Known Folder Move" (on by default on many Windows 11 /
    Microsoft 365 setups), which relocates Documents to
    ``%USERPROFILE%\\OneDrive\\Documents``, or via Group Policy folder
    redirection to a network share. Reading the actual "Personal" shell
    folder from the registry avoids guessing wrong in that case.

    Mirrors Java's ``ModManagerConfig.getDocumentsPath()``, which shells out
    to ``reg query`` and parses its text output. Using the stdlib ``winreg``
    module directly is simpler and avoids spawning a subprocess.

    Returns None (falls back to the plain default) when not running on
    Windows, or on any registry/lookup failure.
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg  # Windows-only stdlib module; unavailable elsewhere

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            raw_value, _ = winreg.QueryValueEx(key, "Personal")
        expanded = os.path.expandvars(raw_value)
        path = Path(expanded)
        return path if path.is_absolute() else None
    except OSError:
        return None


class SettingsService:
    """Loads and saves application settings as JSON.

    The settings file lives in the platform-appropriate user-data directory
    (Linux: ~/.local/share/FSModManager/, Windows: %APPDATA%/FSModManager/).

    Default paths mirror Java ModManagerConfig:
      source_mod_folder      = <Documents>/My Games/FarmingSimulator2022/mods
      mod_collection_folder  = <Documents>/My Games/FarmingSimulator2022/LS_mods
      savegame_path          = <Documents>/My Games/FarmingSimulator2022

    If the default game directory does not exist on first run, the optional
    `ask_for_path` callback is invoked so the GUI can prompt the user.
    The callback receives no arguments and must return the chosen game-home
    path as a string.  Pass None to skip prompting (useful in tests and for
    the service layer itself – the GUI wires up the real dialog in Phase 11).
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DATA_DIR
        self._settings_file = self._data_dir / _SETTINGS_FILE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def settings_file(self) -> Path:
        return self._settings_file

    def exists(self) -> bool:
        """Return True if a settings file has already been saved."""
        return self._settings_file.exists()

    def load(self, ask_for_path: Callable[[], str] | None = None) -> Settings:
        """Load settings from disk.

        If no settings file exists yet, default settings are created.
        When the default game directory is not found, `ask_for_path` is
        called to let the caller supply a path (e.g. via a GUI dialog).
        """
        if self._settings_file.exists():
            return Settings.from_json(
                self._settings_file.read_text(encoding="utf-8")
            )
        return self._build_defaults(ask_for_path)

    def save(self, settings: Settings) -> None:
        """Persist settings to disk (creates directories if needed)."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(settings.to_json(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_defaults(self, ask_for_path: Callable[[], str] | None) -> Settings:
        game_home = self._find_game_home(ask_for_path)
        return Settings(
            source_mod_folder=str(game_home / "mods"),
            mod_collection_folder=str(game_home / "LS_mods"),
            savegame_path=str(game_home),
        )

    @staticmethod
    def _find_game_home(ask_for_path: Callable[[], str] | None) -> Path:
        """Return the FS22 game-home directory.

        Resolves the real Documents folder first (via the Windows registry
        on Windows, to correctly handle a redirected/OneDrive Documents
        folder; falls back to ``~/Documents`` everywhere else or if that
        lookup fails), then checks the standard
        ``<Documents>/My Games/FarmingSimulator2022`` location.  Falls back
        to the `ask_for_path` callback if that directory does not exist.
        """
        documents_dir = _windows_documents_dir() or (Path.home() / "Documents")
        default = documents_dir / _FS22_SUBPATH
        if default.exists():
            return default
        if ask_for_path is not None:
            return Path(ask_for_path())
        # Neither found nor asked – return the standard path anyway so the
        # caller gets something sensible; validation happens in the GUI.
        return default
