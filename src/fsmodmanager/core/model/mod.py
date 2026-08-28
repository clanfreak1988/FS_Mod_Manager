import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# FS itself rejects a mod at load time with "Invalid mod name '<name>'!
# Characters allowed: (_, A-Z, a-z, 0-9). The first character must not be a
# digit" if the ZIP filename (without extension) doesn't match this pattern -
# most commonly caused by a space or "(1)" suffix from a duplicate download.
_VALID_MOD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_valid_mod_name(filename: str) -> bool:
    """True if `filename`'s stem (without extension) satisfies FS's mod-name rule."""
    return bool(_VALID_MOD_NAME_RE.match(Path(filename).stem))


def sanitize_mod_name(filename: str) -> str:
    """Best-effort fix for a filename FS would reject, preserving as much of
    the original as possible: drops a browser's duplicate-download suffix
    (" (1)"), strips every remaining disallowed character, and prefixes an
    underscore if that still leaves a leading digit. Only a suggestion - the
    caller lets the user review/edit it before it's applied."""
    p = Path(filename)
    stem = re.sub(r"\s*\(\d+\)\s*$", "", p.stem)
    stem = re.sub(r"[^A-Za-z0-9_]", "", stem)
    if not stem:
        stem = "Mod"
    elif stem[0].isdigit():
        stem = f"_{stem}"
    return f"{stem}{p.suffix}"


@dataclass
class Mod:
    """Represents a single FS mod ZIP file with its parsed metadata.

    Fields map 1:1 to Java Mod.java. icon_path is runtime-only (not serialized)
    and replaces the JavaFX ImageView.
    """

    filename: str       # ZIP filename, e.g. "FS25_SomeMod.zip"
    title: str          # modDesc.xml → title
    author: str         # modDesc.xml → author
    version: str        # modDesc.xml → version
    icon_filename: str  # icon path inside the ZIP (may be .dds or .png)
    # New, no Java equivalent: True if modDesc.xml has a <maps> element,
    # i.e. this mod adds/replaces a map. Lets the GUI highlight map mods.
    is_map: bool = False
    icon_path: Path | None = field(default=None, compare=False, repr=False)

    @property
    def has_invalid_name(self) -> bool:
        """True if FS would reject this mod with "Invalid mod name ...!" at load time."""
        return not is_valid_mod_name(self.filename)

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "title": self.title,
            "author": self.author,
            "version": self.version,
            "icon_filename": self.icon_filename,
            "is_map": self.is_map,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Mod":
        return cls(
            filename=data["filename"],
            title=data["title"],
            author=data["author"],
            version=data["version"],
            icon_filename=data["icon_filename"],
            is_map=bool(data.get("is_map", False)),
        )

    @classmethod
    def from_json(cls, raw: str) -> "Mod":
        return cls.from_dict(json.loads(raw))
