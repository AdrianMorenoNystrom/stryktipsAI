from datetime import timedelta
import json
from app.storage import iso, now_utc
from app.stryktipset.repository import digest, fixture_key
from app.market.config import MarketConfig, SPORT_KEYS
from app.market.consensus import aware, consensus, match_event
from app.market.provider import TheOddsApiProvider, OddsUnavailable


class MarketService:
    def __init__(self, repo, config=None, provider=None):
        self.repo = repo
        self.config = config or MarketConfig()
        self.provider = provider or TheOddsApiProvider(repo, self.config)

    def update(self, draw):
        report = {'matched': [], 'unresolved': [], 'errors': [], 'configured': bool(self.config.api_key)}
        if not self.config.api_key and isinstance(self.provider, TheOddsApiProvider):
            report['errors'].append('Bookmakerprovider är inte konfigurerad; märkta fallbackodds används där de finns.')
            return report
        if now_utc() >= draw.sales_close_at:
            return {**report, 'closed': True}
        with self.repo.lock('odds-update') as acquired:
            if not acquired:
                return {**report, 'busy': True}
            for league in sorted({m.league for m in draw.matches if m.league in SPORT_KEYS}):
                try:
                    events, request = self.provider.get_upcoming_events(league)
                except OddsUnavailable as exc:
                    report['errors'].append(str(exc))
                    continue
                for match in [m for m in draw.matches if m.league == league]:
                    event = match_event(match, events, self.config)
                    if not event:
                        report['unresolved'].append({'number': match.number, 'reason': 'MARKET MATCH UNRESOLVED'})
                        continue
                    result = consensus(event, aware(request['retrieved_at']), self.config)
                    if not result:
                        report['unresolved'].append({'number': match.number, 'reason': 'No complete fresh bookmaker 1X2'})
                        continue
                    self.save(draw, match, event, request, result)
                    report['matched'].append({'number': match.number, 'bookmakers': result['bookmaker_count'], 'eligible': result['eligible']})
        return report

    def save(self, draw, match, event, request, result):
        at = now_utc()
        identifier = digest(request['id'] + fixture_key(match) + str(draw.draw_number))
        item = {**result, 'id': identifier, 'draw_number': draw.draw_number, 'number': match.number,
            'league':match.league,
            'match_id': match.match_id, 'fixture_key': fixture_key(match), 'provider_event_id': event['id'],
            'recorded_at': iso(at), 'retrieved_at': request['retrieved_at'], 'source_updated_at': result['newest_bookmaker_update'],
            'provider': 'the-odds-api', 'source': 'bookmaker_consensus', 'raw_reference': request['raw_reference'], 'request_id': request['id']}
        with self.repo.connection() as con:
            earlier=[json.loads(r[0]) for r in con.execute('SELECT payload FROM consensus_snapshots WHERE draw_number=? AND number=? AND fixture_key=? AND retrieved_at<=? AND recorded_at<=? ORDER BY retrieved_at,recorded_at,id',(draw.draw_number,match.number,fixture_key(match),item['retrieved_at'],iso(at)))]
            item['movement']={'since_previous':{k:item['consensus'][k]-earlier[-1]['consensus'][k] for k in ('home','draw','away')} if earlier else None,'since_first':{k:item['consensus'][k]-earlier[0]['consensus'][k] for k in ('home','draw','away')} if earlier else None}
            con.execute('INSERT OR IGNORE INTO consensus_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (identifier, draw.draw_number, match.number, match.match_id, fixture_key(match), event['id'], iso(at), item['retrieved_at'], item['source_updated_at'], int(item['eligible']), json.dumps(item)))
            for book in result['bookmakers']:
                con.execute('INSERT OR IGNORE INTO bookmaker_observations VALUES (?,?,?,?)', (identifier, book['bookmaker'], book['last_update'], json.dumps(book)))

    def candidates(self, number, at):
        with self.repo.connection() as con:
            rows = con.execute('SELECT number,payload FROM consensus_snapshots WHERE draw_number=? AND eligible=1 AND recorded_at<=? AND retrieved_at<=? AND source_updated_at<=? AND retrieved_at>=? ORDER BY retrieved_at,recorded_at,id',
                (number, iso(at), iso(at), iso(at), iso(at - timedelta(seconds=self.config.cached_max_seconds))))
            candidates={r[0]:json.loads(r[1]) for r in rows}
            health={r[0]:json.loads(r[1]) for r in con.execute('SELECT league,payload FROM (SELECT league,payload,ROW_NUMBER() OVER(PARTITION BY league ORDER BY retrieved_at DESC) AS rank FROM odds_requests WHERE retrieved_at<=?) recent WHERE rank=1',(iso(at),))}
            for candidate in candidates.values():
                last=health.get(candidate.get('league'),{})
                candidate['provider_degraded']=bool(last and (last.get('status')!=200 or not last.get('schema_valid',True)))
            return candidates

    def select(self, match, candidate, source_odds, at):
        if candidate and candidate['fixture_key'] == fixture_key(match):
            age = (at - aware(candidate['retrieved_at'])).total_seconds()
            source = 'bookmaker_consensus' if age <= self.config.fresh_seconds and not candidate.get('provider_degraded') else 'cached_consensus'
            return {**candidate, 'source': source, 'market_source': source, 'odds': candidate['average_odds'], 'market': candidate['consensus']}
        if source_odds:
            source = 'manual' if source_odds['provider'] == 'manual' else 'svenska_spel_odds'
            return {**source_odds, 'market_source': source, 'bookmaker_count': 0}
        return None

    def history(self, draw, number, at):
        with self.repo.connection() as con:
            rows = con.execute('SELECT payload FROM consensus_snapshots WHERE draw_number=? AND number=? AND recorded_at<=? AND retrieved_at<=? AND source_updated_at<=? ORDER BY retrieved_at,recorded_at,id', (draw, number, iso(at), iso(at), iso(at)))
            return [json.loads(row[0]) for row in rows]

    def health(self):
        with self.repo.connection() as con:
            last = con.execute('SELECT payload FROM odds_requests ORDER BY retrieved_at DESC LIMIT 1').fetchone()
            successful = (json.loads(r[0]) for r in con.execute('SELECT payload FROM odds_requests WHERE status=200 ORDER BY retrieved_at DESC'))
            success = next((r['retrieved_at'] for r in successful if r.get('schema_valid', True)), None)
        request = json.loads(last[0]) if last else None
        return {'configured': bool(self.config.api_key), 'status': 'Healthy' if request and request['status'] == 200 and request.get('schema_valid', True) else 'Degraded' if success else 'Unavailable',
            'last_successful_fetch': success, 'last_attempt': request['retrieved_at'] if request else None, 'quota': request.get('quota') if request else None}
