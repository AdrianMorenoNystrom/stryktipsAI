"""Deterministic team/time/competition matching and two explicit consensus definitions."""
from datetime import datetime, timezone
from statistics import mean, median, pstdev
from app.schemas import Odds
from app.services.probabilities import devig
from app.stryktipset.teams import map_team
from app.market.config import SPORT_KEYS

OUTCOMES = ('home', 'draw', 'away')


def aware(value):
    if not isinstance(value,str):raise ValueError('Timestamp missing')
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not at.tzinfo:
        raise ValueError('Timestamp lacks timezone')
    return at.astimezone(timezone.utc)


def match_event(match, events, config):
    if not match.home_team_id or not match.away_team_id or not match.kickoff_at:
        return None
    candidates = []
    for event in events:
        try:
            if (event['sport_key'] == SPORT_KEYS.get(match.league)
                and map_team(event['home_team'])[1] == match.home_team_id
                and map_team(event['away_team'])[1] == match.away_team_id
                and abs((aware(event['commence_time']) - match.kickoff_at).total_seconds()) <= config.kickoff_tolerance_seconds
                and isinstance(event['id'], str) and event['id']):
                candidates.append(event)
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
    return candidates[0] if len(candidates) == 1 else None


def consensus(event, retrieved_at, config):
    books, seen, rejected = [], set(), []
    raw_books=event.get('bookmakers', [])
    if not isinstance(raw_books,list):return None
    for bookmaker in raw_books:
        name = bookmaker.get('key') if isinstance(bookmaker, dict) else None
        try:
            if not name or name in seen or name in config.exclude_bookmakers:
                raise ValueError('Excluded or duplicate bookmaker')
            seen.add(name)
            markets = [m for m in bookmaker['markets'] if m.get('key') == 'h2h']
            if len(markets) != 1:
                raise ValueError('No unique h2h market')
            market = markets[0]
            updated = aware(market.get('last_update') or bookmaker['last_update'])
            age = (retrieved_at - updated).total_seconds()
            if not 0 <= age <= config.bookmaker_max_age_seconds:
                raise ValueError('Stale or future bookmaker')
            expected = (event['home_team'], 'Draw', event['away_team'])
            values = market['outcomes']
            if len(values) != 3 or {v['name'] for v in values} != set(expected):
                raise ValueError('Incomplete 1X2')
            by_name = {v['name']: v['price'] for v in values}
            if any(isinstance(v, bool) for v in by_name.values()):
                raise ValueError('Boolean price')
            odds = Odds(**dict(zip(OUTCOMES, [by_name[n] for n in expected]))).model_dump()
            books.append({'bookmaker': name, 'title': bookmaker.get('title', name), 'odds': odds,
                'probabilities': devig(odds), 'last_update': updated.isoformat()})
        except (KeyError, TypeError, ValueError, AttributeError):
            rejected.append(name)
    if not books:
        return None
    averaged_odds = {k: mean(b['odds'][k] for b in books) for k in OUTCOMES}
    robust = {k: median(b['probabilities'][k] for b in books) for k in OUTCOMES}
    total = sum(robust.values())
    dispersion = {k: pstdev(b['probabilities'][k] for b in books) for k in OUTCOMES}
    return {'bookmakers': books, 'bookmaker_count': len(books), 'average_odds': averaged_odds,
        'consensus': devig(averaged_odds), 'median': {k: v / total for k, v in robust.items()},
        'dispersion': dispersion, 'oldest_bookmaker_update': min(b['last_update'] for b in books),
        'newest_bookmaker_update': max(b['last_update'] for b in books),
        'eligible': len(books) >= config.minimum_bookmakers, 'rejected_bookmakers': rejected,
        'confidence': 'sufficient_coverage' if len(books) >= config.minimum_bookmakers else 'insufficient_coverage',
        'definition': 'A: arithmetic mean decimal odds then proportional de-vig; B: normalized coordinate median of de-vig probabilities'}
