import hashlib
from app.schemas import MatchInput
from app.services.teams import team_id


def match_id(match: MatchInput) -> str:
    # Date and normalized teams identify a fixture across coupon and provider aliases.
    return hashlib.sha256(f"{match.date}|{match.league}|{team_id(match.homeTeam)}|{team_id(match.awayTeam)}".encode()).hexdigest()[:32]
