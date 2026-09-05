"""GameProfile – one Farming Simulator installation the manager works with.

New, no Java equivalent. The Java version (and every earlier Python version)
knew exactly one set of folders, stored flat in Settings. Supporting several
FS versions side by side means those folders - plus the two pieces of state
that belong to a specific installation rather than to the application - move
into a named profile, of which Settings holds a list.

Per profile, not global:
  • the three paths
  • savegames_read  – FS22's savegames have never been imported just because
    FS25's were, so the one-time import prompt must be per installation
  • active_modpack  – a configuration name only exists within the profile
    whose collection folder holds its JSON file
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# "FarmingSimulator2025" → group(2) == "25". Anchored at both ends so a
# differently named folder falls through to the generic default below.
_FS_DIR_RE = re.compile(r"^FarmingSimulator(\d{2})(\d{2})$", re.IGNORECASE)

DEFAULT_PROFILE_NAME = "Standard"


def derive_profile_name(game_home: str) -> str:
    """Suggest a profile name from a game-home path.

    "…/My Games/FarmingSimulator2025" → "FS25". Used when migrating an old
    settings file that has no profiles yet, so the single profile the user
    ends up with is already named after the version it points at instead of
    something generic.
    """
    match = _FS_DIR_RE.match(Path(game_home).name)
    return f"FS{match.group(2)}" if match else DEFAULT_PROFILE_NAME


@dataclass
class GameProfile:
    """One FS installation: its folders plus its installation-specific state."""

    name: str
    source_mod_folder: str        # FS mods dir (symlinks live here)
    mod_collection_folder: str    # where the real ZIPs are stored
    savegame_path: str
    savegames_read: bool = False
    active_modpack: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source_mod_folder": self.source_mod_folder,
            "mod_collection_folder": self.mod_collection_folder,
            "savegame_path": self.savegame_path,
            "savegames_read": self.savegames_read,
            "active_modpack": self.active_modpack,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameProfile":
        return cls(
            name=data["name"],
            source_mod_folder=data["source_mod_folder"],
            mod_collection_folder=data["mod_collection_folder"],
            savegame_path=data["savegame_path"],
            savegames_read=bool(data.get("savegames_read", False)),
            active_modpack=data.get("active_modpack", ""),
        )
