"""Shared filesystem locations for app-level data (settings, logs).

Single source of truth for the platform-appropriate user-data directory, so
main.py (logging setup), SettingsService, and the GUI (open-log-file button)
don't each derive it separately and risk drifting apart.
"""
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "FSModManager"
DATA_DIR = Path(user_data_dir(APP_NAME))
LOG_FILE = DATA_DIR / "fsmodmanager.log"
