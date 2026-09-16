"""Reuse the canonical team layer; exact aliases only, never fuzzy automatic guesses."""
from functools import lru_cache
from pathlib import Path
import json
from app.config import DATA
from app.services import teams


@lru_cache(maxsize=1)
def canonical_names() -> dict[str, str]:
    path = DATA / "processed" / "matches.parquet"
    names = set(teams.ALIASES)
    registry=Path(__file__).resolve().parents[1]/'canonical_teams.json'
    if registry.exists():names.update(json.loads(registry.read_text(encoding='utf-8')))
    if path.exists():
        import pandas as pd
        frame = pd.read_parquet(path, columns=["home_team", "away_team"])
        names.update(frame.home_team.dropna())
        names.update(frame.away_team.dropna())
    return {teams.team_id(name): teams.normalize_team(name) for name in names}


def map_team(name: str) -> tuple[str, str | None]:
    normalized = teams.normalize_team(name)
    identifier = teams.team_id(name)
    return canonical_names().get(identifier, normalized), identifier if identifier in canonical_names() else None


def save_alias(alias: str, canonical: str) -> dict:
    identifier = teams.team_id(canonical)
    if identifier not in canonical_names():
        raise ValueError("Välj ett befintligt canonical lag från lagsökningen.")
    canonical = canonical_names()[identifier]
    if teams.team_id(alias) in canonical_names() and teams.team_id(alias) != identifier:
        raise ValueError("Aliaset är redan ett annat canonical lag.")
    if teams.key(alias) in teams.MAPPING and teams.team_id(alias) != identifier:
        raise ValueError("Aliaset pekar redan på ett annat lag.")
    if not teams.key(alias):
        raise ValueError("Alias saknas.")
    path = teams.Path(teams.__file__).parents[1] / "team_aliases.json"
    values = json.loads(path.read_text(encoding="utf-8"))
    values[canonical] = sorted(set([*values.get(canonical, []), alias]))
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    teams.ALIASES.update(values)
    teams.MAPPING.update({teams.key(a): name for name, aliases in values.items() for a in [name, *aliases]})
    canonical_names.cache_clear()
    return {"alias": alias, "canonical": canonical, "team_id": identifier}
