import json
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings, stored as JSON via the settings service.

    Fields map 1:1 to ModManagerConfig.java properties.
    Defaults match the Java defaults.
    """

    source_mod_folder: str        # PROP_SOURCE_MOD_FOLDER  – FS mods dir (symlinks live here)
    mod_collection_folder: str    # PROP_MOD_COLLECTION_FOLDER – where real ZIPs are stored
    savegame_path: str            # PROP_SAVEGAME_PATH
    savegames_read: bool = False  # PROP_SAVEGAMES_READ
    active_modpack: str = ""      # PROP_MODPACK_ACTIVE – empty string means none active
    visible_icon_column: bool = True   # PROP_VISIBLE_ICON_COLUMN
    scene_width: float = 1150.0   # PROP_SCENE_WIDTH
    scene_height: float = 700.0   # PROP_SCENE_HEIGHT
    theme: str = "system"         # new, no Java equivalent – "system" | "light" | "dark"

    def to_dict(self) -> dict:
        return {
            "source_mod_folder": self.source_mod_folder,
            "mod_collection_folder": self.mod_collection_folder,
            "savegame_path": self.savegame_path,
            "savegames_read": self.savegames_read,
            "active_modpack": self.active_modpack,
            "visible_icon_column": self.visible_icon_column,
            "scene_width": self.scene_width,
            "scene_height": self.scene_height,
            "theme": self.theme,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        return cls(
            source_mod_folder=data["source_mod_folder"],
            mod_collection_folder=data["mod_collection_folder"],
            savegame_path=data["savegame_path"],
            savegames_read=bool(data.get("savegames_read", False)),
            active_modpack=data.get("active_modpack", ""),
            visible_icon_column=bool(data.get("visible_icon_column", True)),
            scene_width=float(data.get("scene_width", 1150.0)),
            scene_height=float(data.get("scene_height", 700.0)),
            theme=data.get("theme", "system"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "Settings":
        return cls.from_dict(json.loads(raw))
