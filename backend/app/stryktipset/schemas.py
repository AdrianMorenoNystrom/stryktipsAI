from datetime import date, datetime
from typing import Literal
from pydantic import Field
from app.schemas import Schema, Odds, Probabilities


class DrawMatch(Schema):
    number: int
    match_id: str
    provider_event_id: str | None
    home_team: str
    away_team: str
    source_home_team: str
    source_away_team: str
    home_team_id: str | None
    away_team_id: str | None
    kickoff_at: datetime | None
    competition: str | None
    league: str | None
    model_coverage: bool
    status: str | None
    cancelled: bool = False
    crowd: Probabilities | None
    crowd_source_updated_at: datetime | None
    market_odds: Odds | None
    issues: list[str] = Field(default_factory=list)


class Draw(Schema):
    draw_number: int
    draw_date: date
    sales_close_at: datetime
    sales_open_at: datetime | None
    status: Literal["upcoming", "open", "closed", "completed"]
    source_status: str
    retrieved_at: datetime
    row_price: float | None
    provider: str = "svenska-spel"
    source: str
    raw_id: str
    matches: list[DrawMatch]
    issues: list[str] = Field(default_factory=list)


class ResultMatch(Schema):
    number: int
    provider_event_id: str | None
    outcome: Literal["1", "X", "2"] | None
    home_goals: int | None
    away_goals: int | None
    cancelled: bool = False


class Payout(Schema):
    correct: Literal[10, 11, 12, 13]
    winners: int | None
    amount: float | None
    currency: str = "SEK"


class DrawResult(Schema):
    draw_number: int
    completed: bool
    cancelled: bool
    matches: list[ResultMatch]
    payouts: list[Payout]
    retrieved_at: datetime
    source: str
    raw_id: str
