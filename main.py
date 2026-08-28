import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from fsmodmanager.core.app_paths import DATA_DIR, LOG_FILE
from fsmodmanager.core.service.collection_service import CollectionService
from fsmodmanager.core.service.config_service import ConfigService
from fsmodmanager.core.service.export_service import ExportService
from fsmodmanager.core.service.folder_move_service import FolderMoveService
from fsmodmanager.core.service.link_service import LinkService
from fsmodmanager.core.service.mod_rename_service import ModRenameService
from fsmodmanager.core.service.settings_service import SettingsService
from fsmodmanager.gui.icon import app_icon
from fsmodmanager.gui.main_window import MainWindow
from fsmodmanager.gui.theme import apply_theme
from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel

_LOG_DIR = DATA_DIR
_LOG_FILE = LOG_FILE


def _setup_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(sh)

    # File handler – rotating, max 1 MB, keep 3 backups
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        _LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)

    # PIL logs its own internal plugin-discovery chatter at DEBUG (e.g. missing
    # optional 'olefile' for legacy Fpx/Mic formats we never use). Harmless,
    # but noisy at root DEBUG level - raise just this logger's threshold.
    logging.getLogger("PIL").setLevel(logging.INFO)


_setup_logging()
log = logging.getLogger(__name__)


def _configs_dir(settings) -> Path:
    """Derive config JSON directory from the collection folder path."""
    return Path(settings.mod_collection_folder).parent / "LS_sg_config"


def main() -> None:
    app = QApplication(sys.argv)
    # Sets the taskbar/dock icon (and the default for any window that
    # doesn't set its own). Mirrors Java's primaryStage.getIcons().add(...).
    app.setWindowIcon(app_icon())

    settings_svc = SettingsService()
    log.info("Log file: %s", _LOG_FILE)
    log.info("Settings file: %s", settings_svc.settings_file)

    # Applied before the window is constructed/shown, so there's no visible
    # flash from the default theme to the configured one. A plain peek at
    # settings (no ask_for_path callback) - doesn't prompt or write anything
    # even on a genuinely first run; MainViewModel.initialize() reloads the
    # real settings (and re-applies the theme, in case ask_for_path changes
    # anything relevant) once the main window is shown.
    apply_theme(settings_svc.load(ask_for_path=None).theme)

    vm = MainViewModel(
        settings_service=settings_svc,
        # Placeholder ConfigService – replaced by initialize() via factory
        # once the real settings (and their paths) are known.
        config_service=ConfigService(configs_dir=Path.home()),
        link_service=LinkService(),
        collection_service=CollectionService(),
        folder_move_service=FolderMoveService(),
        export_service=ExportService(),
        mod_rename_service=ModRenameService(),
        configs_dir_factory=_configs_dir,
    )

    window = MainWindow(view_model=vm)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
