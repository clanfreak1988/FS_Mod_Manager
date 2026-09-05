import json
from dataclasses import dataclass, field, replace

from fsmodmanager.core.model.game_profile import GameProfile, derive_profile_name


@dataclass
class Settings:
    """Application settings, stored as JSON via the settings service.

    The first eight fields map 1:1 to ModManagerConfig.java properties;
    defaults match the Java defaults. `theme`, `profiles` and
    `active_profile` are additions without a Java equivalent.

    Profiles vs. top-level fields
    -----------------------------
    `profiles` holds one GameProfile per supported FS installation. The
    top-level path fields (plus savegames_read / active_modpack) always
    mirror the *active* profile: every consumer in the app keeps reading
    `settings.source_mod_folder` as before, and an older build - whose
    Settings.from_dict() requires those keys - can still read a settings
    file written by this one.

    __post_init__ therefore guarantees at least one profile exists, so a
    settings file written before profiles existed migrates on load into a
    single profile named after the game folder it points at.
    """

    source_mod_folder: str        # PROP_SOURCE_MOD_FOLDER  – FS mods dir (symlinks live here)
    mod_collection_folder: str    # PROP_MOD_COLLECTION_FOLDER – where real ZIPs are stored
    savegame_path: str            # PROP_SAVEGAME_PATH
    savegames_read: bool = False  # PROP_SAVEGAMES_READ            – per profile
    active_modpack: str = ""      # PROP_MODPACK_ACTIVE            – per profile, "" means none
    visible_icon_column: bool = True   # PROP_VISIBLE_ICON_COLUMN
    scene_width: float = 1150.0   # PROP_SCENE_WIDTH
    scene_height: float = 700.0   # PROP_SCENE_HEIGHT
    theme: str = "system"         # new, no Java equivalent – "system" | "light" | "dark"
    profiles: list[GameProfile] = field(default_factory=list)
    active_profile: str = ""

    def __post_init__(self) -> None:
        if not self.profiles:
            # Migration / fresh start: the flat fields become profile #1.
            self.profiles = [
                GameProfile(
                    name=derive_profile_name(self.savegame_path),
                    source_mod_folder=self.source_mod_folder,
                    mod_collection_folder=self.mod_collection_folder,
                    savegame_path=self.savegame_path,
                    savegames_read=self.savegames_read,
                    active_modpack=self.active_modpack,
                )
            ]
        if self.active_profile not in self.profile_names:
            # Unknown (or unset) active profile: trust the profile list
            # rather than the mirrored fields and re-apply the first entry.
            self.apply_profile(self.profiles[0].name)

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    @property
    def profile_names(self) -> list[str]:
        return [p.name for p in self.profiles]

    @property
    def active_game_profile(self) -> GameProfile:
        """The profile the top-level fields mirror (always present)."""
        for profile in self.profiles:
            if profile.name == self.active_profile:
                return profile
        return self.profiles[0]

    def apply_profile(self, name: str) -> None:
        """Make `name` the active profile: copy its values to the top level."""
        profile = next(p for p in self.profiles if p.name == name)
        self.active_profile = profile.name
        self.source_mod_folder = profile.source_mod_folder
        self.mod_collection_folder = profile.mod_collection_folder
        self.savegame_path = profile.savegame_path
        self.savegames_read = profile.savegames_read
        self.active_modpack = profile.active_modpack

    def sync_active_profile(self) -> None:
        """Write the top-level fields back into the active profile entry.

        Called before persisting, so edits made through the existing
        settings dialog (or activate_config() setting active_modpack) land
        in the profile they belong to. Replaces the entry instead of
        mutating it, so a shallow copy of a Settings object can never write
        through into the original's profile list.
        """
        active = self.active_game_profile
        updated = replace(
            active,
            source_mod_folder=self.source_mod_folder,
            mod_collection_folder=self.mod_collection_folder,
            savegame_path=self.savegame_path,
            savegames_read=self.savegames_read,
            active_modpack=self.active_modpack,
        )
        self.profiles = [updated if p is active else p for p in self.profiles]

    # ------------------------------------------------------------------
    # (De-)serialisation
    # ------------------------------------------------------------------

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
            "profiles": [p.to_dict() for p in self.profiles],
            "active_profile": self.active_profile,
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
            profiles=[GameProfile.from_dict(p) for p in data.get("profiles", [])],
            active_profile=data.get("active_profile", ""),
        )

    @classmethod
    def from_json(cls, raw: str) -> "Settings":
        return cls.from_dict(json.loads(raw))
