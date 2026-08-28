import json
from dataclasses import dataclass, field


@dataclass
class Configuration:
    """A named set of mod filenames (= one ModPack in the Java version).

    mod_filenames is kept case-insensitively sorted, matching Java's
    TreeMap / sort(String.CASE_INSENSITIVE_ORDER) behaviour.
    """

    name: str
    mod_filenames: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mod_filenames = sorted(self.mod_filenames, key=str.casefold)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mod_filenames": self.mod_filenames,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        return cls(
            name=data["name"],
            mod_filenames=data.get("mod_filenames", []),
        )

    @classmethod
    def from_json(cls, raw: str) -> "Configuration":
        return cls.from_dict(json.loads(raw))
