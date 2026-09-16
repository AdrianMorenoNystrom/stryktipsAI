from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SignalType(StrEnum):
    PLAYER_OUT = "PLAYER_OUT"
    PLAYER_DOUBTFUL = "PLAYER_DOUBTFUL"
    PLAYER_RETURN = "PLAYER_RETURN"
    PLAYER_SUSPENDED = "PLAYER_SUSPENDED"
    EXPECTED_STARTER_OUT = "EXPECTED_STARTER_OUT"
    EXPECTED_LINEUP_CHANGE = "EXPECTED_LINEUP_CHANGE"
    ROTATION_EXPECTED = "ROTATION_EXPECTED"
    HEAVY_ROTATION_EXPECTED = "HEAVY_ROTATION_EXPECTED"
    FITNESS_LIMITATION = "FITNESS_LIMITATION"
    MANAGER_CHANGE = "MANAGER_CHANGE"
    TACTICAL_CHANGE = "TACTICAL_CHANGE"
    FIXTURE_CONGESTION = "FIXTURE_CONGESTION"
    REST_ADVANTAGE = "REST_ADVANTAGE"
    REST_DISADVANTAGE = "REST_DISADVANTAGE"
    INTERNAL_ISSUE = "INTERNAL_ISSUE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"


class NewsArticle(StrictModel):
    id: str
    version_id: str
    title: str
    url: HttpUrl
    publisher: str
    published_at: AwareDatetime | None
    retrieved_at: AwareDatetime
    content: str = ""
    snippet: str = ""
    source_tier: Annotated[int, Field(ge=1, le=4)]
    detected_team_ids: list[str]
    query: str
    raw_path: str
    content_hash: str


class ExtractedSignal(StrictModel):
    type: SignalType
    team: str
    player: str | None
    direction: Literal["positive", "negative", "neutral"]
    certainty: Annotated[float, Field(ge=0, le=1)]
    status: Literal["confirmed", "reported", "uncertain"]
    summary: Annotated[str, Field(min_length=1, max_length=400)]
    evidence: Annotated[str, Field(min_length=5, max_length=800)]
    occurred_at: AwareDatetime | None


class Extraction(StrictModel):
    signals: Annotated[list[ExtractedSignal], Field(max_length=20)]


class PlayerEntity(StrictModel):
    player_id: str
    canonical_name: str
    team_id: str
    aliases: list[str]
    player_importance: float | None = None
