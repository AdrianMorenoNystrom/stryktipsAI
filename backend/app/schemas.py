from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.config import CROWD_TOLERANCE, ROW_COST
from app.services.teams import team_id

Number = Annotated[float, Field(ge=0, le=100)]
Sign = Literal["1", "X", "2"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Probabilities(Schema):
    home: float
    draw: float
    away: float


class Crowd(Schema):
    home: Number
    draw: Number
    away: Number

    @model_validator(mode="after")
    def validate_sum(self) -> "Crowd":
        if abs(self.home + self.draw + self.away - 100) > CROWD_TOLERANCE:
            raise ValueError("Svenska Folkets procent ska summera till 100 (±1 procentenhet).")
        return self

    def normalized(self) -> dict[str, float]:
        total = self.home + self.draw + self.away
        return {k: v / total for k, v in self.model_dump().items()}


class Odds(Schema):
    home: Annotated[float, Field(gt=1, le=10000)]
    draw: Annotated[float, Field(gt=1, le=10000)]
    away: Annotated[float, Field(gt=1, le=10000)]


class Snapshot(Schema):
    recorded_at: datetime | None = None
    valid_at: datetime | None = None
    source: str = "manual"
    retrieved_at: datetime | None = None
    source_updated_at: datetime | None = None


class MatchInput(Schema):
    homeTeam: Annotated[str, Field(min_length=1, max_length=100)]
    awayTeam: Annotated[str, Field(min_length=1, max_length=100)]
    date: date
    league: Annotated[str, Field(min_length=1, max_length=100)]
    marketOdds: Odds
    oddsSnapshot: Snapshot = Field(default_factory=Snapshot)

    @model_validator(mode="after")
    def distinct_teams(self) -> "MatchInput":
        if not team_id(self.homeTeam) or not team_id(self.awayTeam) or team_id(self.homeTeam) == team_id(self.awayTeam):
            raise ValueError("Ange två olika lagnamn.")
        return self


class CouponMatch(MatchInput):
    number: Annotated[int, Field(ge=1, le=13)]
    crowd: Crowd
    crowdSnapshot: Snapshot = Field(default_factory=Snapshot)
    kickoffAt: datetime | None = None
    providerEventId: str | None = None
    crowdMatchId: str | None = None
    competition: str | None = None
    modelCoverage: bool | None = None
    marketSource: str | None = None
    marketQuality: dict | None = None


class Coupon(Schema):
    id: str
    week: Annotated[int, Field(ge=1, le=53)]
    date: date
    demo: bool = False
    drawNumber: int | None = None
    salesCloseAt: datetime | None = None
    retrievedAt: datetime | None = None
    dataSource: Literal["manual", "svenska-spel", "demo"] = "manual"
    drawStatus: str | None = None
    matches: Annotated[list[CouponMatch], Field(min_length=13, max_length=13)]

    @model_validator(mode="after")
    def unique_matches(self) -> "Coupon":
        if sorted(m.number for m in self.matches) != list(range(1, 14)):
            raise ValueError("Kupongen ska ha matchnummer 1–13 exakt en gång.")
        identities = [(m.date, team_id(m.homeTeam), team_id(m.awayTeam)) for m in self.matches]
        if len(set(identities)) != 13:
            raise ValueError("Samma match finns flera gånger på kupongen.")
        return self


class AnalyzeRequest(Schema):
    coupon: Coupon
    budget: Annotated[float, Field(ge=ROW_COST, le=1000000)] = 256
    mode: Literal["optimal", "safe", "value"] = "optimal"


class CostRequest(Schema):
    selections: Annotated[list[list[Sign]], Field(min_length=13, max_length=13)]

    @model_validator(mode="after")
    def valid_selections(self) -> "CostRequest":
        if any(not row or len(set(row)) != len(row) for row in self.selections):
            raise ValueError("Varje match måste ha 1–3 unika tecken.")
        return self
