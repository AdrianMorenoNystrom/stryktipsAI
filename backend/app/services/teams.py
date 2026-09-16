import json
import re
import unicodedata
from pathlib import Path


def key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


ALIASES = json.loads((Path(__file__).parents[1] / "team_aliases.json").read_text(encoding="utf-8"))
MAPPING = {key(alias): canonical for canonical, aliases in ALIASES.items() for alias in [canonical, *aliases]}


def normalize_team(name: str) -> str:
    return MAPPING.get(key(name), name.strip())


def team_id(name: str) -> str:
    return key(normalize_team(name))
