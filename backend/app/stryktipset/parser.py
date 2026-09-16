"""Only this module understands Svenska Spel JSON. Missing values never become zero."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from pydantic import ValidationError
from app.schemas import Crowd, Odds, Probabilities
from app.stryktipset.config import STOCKHOLM
from app.stryktipset.schemas import Draw, DrawMatch, DrawResult, ResultMatch, Payout
from app.stryktipset.teams import map_team


class ProviderSchemaError(ValueError):
    pass


def number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ProviderSchemaError("Boolean numeric field")
    try:
        parsed = Decimal(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
        if not parsed.is_finite():
            raise ProviderSchemaError("Non-finite numeric field")
        return float(parsed)
    except InvalidOperation:
        raise ProviderSchemaError("Invalid numeric field") from None


def timestamp(value, required=False) -> datetime | None:
    if value is None or value == "":
        if required:
            raise ProviderSchemaError("Required timestamp missing")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if not parsed.tzinfo:
            raise ValueError("Timezone missing")
        # Observed legacy API sentinel: year 0001 is not a source observation time.
        if parsed.year < 2000:
            if required:
                raise ValueError("Invalid required timestamp")
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ProviderSchemaError("Invalid timestamp") from None


def triplet(raw, cls):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ProviderSchemaError("Invalid outcome object")
    values = {key: number(raw.get(field)) for key, field in (("home", "one"), ("draw", "x"), ("away", "two"))}
    if any(v is None for v in values.values()):
        return None
    try:
        return cls(**values)
    except ValidationError:
        raise ProviderSchemaError("Invalid outcome values") from None


def draw_objects(payload: dict, specific: bool = False) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("error"):
        raise ProviderSchemaError("Provider error or non-object payload")
    if specific:
        result = payload.get("draw")
        if not isinstance(result, dict):
            raise ProviderSchemaError("draw object missing")
        return [result]
    result = payload.get("draws")
    if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
        raise ProviderSchemaError("draws list missing")
    return result


def parse_draw(raw: dict, retrieved_at: datetime, source: str, raw_id: str) -> Draw:
    try:
        if raw.get("productName") != "Stryktipset" or raw.get("productId") != 1:
            raise ProviderSchemaError("Unexpected product")
        draw_number = int(raw["drawNumber"])
        close = timestamp(raw.get("regCloseTime"), required=True)
        opened = timestamp(raw.get("regOpenTime"))
        source_status = raw["drawState"]
        states = {"Open":"open", "NotOpened":"upcoming", "Upcoming":"upcoming", "Closed":"closed", "Ongoing":"closed", "Finished":"closed", "Finalized":"completed", "Cancelled":"closed"}
        if source_status not in states:
            raise ProviderSchemaError(f"Unknown drawState: {source_status}")
        status = states[source_status]
        if status == "open" and close <= retrieved_at:
            status = "closed"
        elif status == "open" and opened and opened > retrieved_at:
            status = "upcoming"
        events = raw["drawEvents"]
        if not isinstance(events, list) or len(events) != 13 or sorted(e["eventNumber"] for e in events) != list(range(1, 14)):
            raise ProviderSchemaError("Expected exactly 13 unique eventNumbers 1-13")
        matches = []
        for event in sorted(events, key=lambda e: e["eventNumber"]):
            match = event["match"]
            participants = match["participants"]
            names = {}
            for side in ("home", "away"):
                selected = [p for p in participants if p.get("type") == side]
                if len(selected) != 1 or not isinstance(selected[0].get("name"), str) or not selected[0]["name"].strip():
                    raise ProviderSchemaError("Missing or ambiguous participant")
                names[side] = selected[0]["name"].strip()
            home, home_id = map_team(names["home"])
            away, away_id = map_team(names["away"])
            if home == away:
                raise ProviderSchemaError("Identical participants")
            competition = match.get("league") or {}
            league = {"Premier League":"E0", "Championship":"E1", "League One":"E2"}.get(competition.get("name")) if competition.get("country", {}).get("isoCode") == "ENG" else None
            issues = []
            for side, identifier in (("home", home_id), ("away", away_id)):
                if identifier is None:
                    issues.append(f"UNMAPPED TEAM: {names[side]}")
            if league is None:
                issues.append("No trained league coverage. Endast dokumenterad oddsbaserad fallback är tillgänglig.")
            try:
                crowd = triplet(event.get("svenskaFolket"), Crowd)
                crowd_time = timestamp((event.get("svenskaFolket") or {}).get("date"))
            except ProviderSchemaError as exc:
                crowd, crowd_time = None, None
                issues.append(f"Ogiltiga folkstreck: {exc}")
            if crowd is None:
                issues.append("Svenska Folket saknas eller är ogiltigt.")
            try:
                odds = triplet(event.get("odds"), Odds)
            except ProviderSchemaError as exc:
                odds = None
                issues.append(f"Ogiltiga odds: {exc}")
            if odds is None:
                issues.append("Aktuella marknadsodds saknas. Ange odds manuellt för analys.")
            kickoff = timestamp(match.get("matchStart"))
            if kickoff is None:
                issues.append("Kickoff saknas; matchen kan inte analyseras.")
            matches.append(DrawMatch(number=event["eventNumber"], match_id=f"ss:{draw_number}:{event['eventNumber']}",
                provider_event_id=str(match["matchId"]) if match.get("matchId") is not None else None,
                home_team=home, away_team=away, source_home_team=names["home"], source_away_team=names["away"],
                home_team_id=home_id, away_team_id=away_id, kickoff_at=kickoff, competition=competition.get("name"), league=league,
                model_coverage=bool(league and home_id and away_id), status=match.get("sportEventStatus"), cancelled=bool(event.get("cancelled", False)),
                crowd=Probabilities(**crowd.normalized()) if crowd else None, crowd_source_updated_at=crowd_time, market_odds=odds, issues=issues))
        if len({m.provider_event_id for m in matches if m.provider_event_id is not None}) != sum(m.provider_event_id is not None for m in matches):
            raise ProviderSchemaError("Duplicate provider event id")
        issues = []
        if raw.get("regBetDisabled") not in (None, "NotDisabled") or source_status == "Cancelled":
            issues.append("Provider anger att omgången inte är öppen för spel.")
        return Draw(draw_number=draw_number, draw_date=close.astimezone(STOCKHOLM).date(), sales_close_at=close, sales_open_at=opened,
            status=status, source_status=source_status, retrieved_at=retrieved_at, row_price=number(raw.get("rowPrice")), source=source, raw_id=raw_id, matches=matches, issues=issues)
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        if isinstance(exc, ProviderSchemaError):
            raise
        raise ProviderSchemaError(f"Invalid draw structure ({type(exc).__name__})") from None


def parse_result(payload: dict, retrieved_at: datetime, source: str, raw_id: str, expected_draw: int) -> DrawResult:
    try:
        raw = payload["result"]
        if payload.get("error") or not isinstance(raw, dict) or raw.get("drawNumber") != expected_draw or raw.get("productName") != "Stryktipset":
            raise ProviderSchemaError("Result draw/product mismatch")
        events = raw["events"]
        if len(events) != 13 or sorted(e["eventNumber"] for e in events) != list(range(1,14)):
            raise ProviderSchemaError("Expected 13 result events")
        matches = []
        for event in sorted(events, key=lambda e: e["eventNumber"]):
            outcome = event.get("outcome")
            if outcome not in (None, "", "1", "X", "2"):
                raise ProviderSchemaError("Unknown official outcome")
            score = event.get("outcomeScore") or {}
            goals = [number(score.get(side)) for side in ("home", "away")]
            if any(g is not None and (g < 0 or not g.is_integer()) for g in goals):
                raise ProviderSchemaError("Invalid goals")
            if all(g is not None for g in goals) and outcome and not event.get("cancelled"):
                calculated = "1" if goals[0] > goals[1] else "2" if goals[0] < goals[1] else "X"
                if calculated != outcome:
                    raise ProviderSchemaError("Official outcome contradicts score")
            matches.append(ResultMatch(number=event["eventNumber"], provider_event_id=str(event["matchId"]) if event.get("matchId") is not None else None,
                outcome=outcome or None, home_goals=int(goals[0]) if goals[0] is not None else None,
                away_goals=int(goals[1]) if goals[1] is not None else None, cancelled=bool(event.get("cancelled", False))))
        payouts = []
        for item in raw.get("distribution") or []:
            level = re.fullmatch(r"(1[0-3]) r\u00e4tt", item.get("name", ""))
            if not level:
                raise ProviderSchemaError("Unknown payout level")
            winners, amount = number(item.get("winners")), number(item.get("amount"))
            if winners is not None and (winners < 0 or not winners.is_integer()) or amount is not None and amount < 0:
                raise ProviderSchemaError("Invalid payout")
            payouts.append(Payout(correct=int(level[1]), winners=int(winners) if winners is not None else None, amount=amount))
        if len({p.correct for p in payouts}) != len(payouts):
            raise ProviderSchemaError("Duplicate payout levels")
        return DrawResult(draw_number=expected_draw, completed=all(m.outcome for m in matches), cancelled=bool(raw.get("cancelled", False)),
            matches=matches, payouts=payouts, retrieved_at=retrieved_at, source=source, raw_id=raw_id)
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        if isinstance(exc, ProviderSchemaError):
            raise
        raise ProviderSchemaError(f"Invalid result structure ({type(exc).__name__})") from None
