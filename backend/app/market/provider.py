"""Documented The Odds API v4. Keys never enter public metadata or HTTP logs."""
from datetime import datetime, timedelta
import hashlib
import json
import logging
import time
from typing import Protocol
from uuid import uuid4
import httpx
from app.storage import iso, now_utc
from app.market.config import SPORT_KEYS

BASE = 'https://api.the-odds-api.com/v4/sports'


class OddsUnavailable(RuntimeError):
    pass


class OddsProvider(Protocol):
    def get_upcoming_events(self, league: str): ...
    def get_event_odds(self, league: str, event_id: str): ...


class TheOddsApiProvider:
    def __init__(self, repo, config, client=None):
        self.repo, self.config, self.client = repo, config, client

    def get_upcoming_events(self, league):
        return self._get(league)

    def get_event_odds(self, league, event_id):
        return self._get(league, event_id)

    def _get(self, league, event_id=None):
        if league not in SPORT_KEYS:
            raise OddsUnavailable('Liga saknar bookmakerprovider.')
        endpoint = f'{BASE}/{SPORT_KEYS[league]}' + (f'/events/{event_id}/odds' if event_id else '/odds')
        # Key-free endpoint including query semantics is the cache identity.
        identity = endpoint + '?regions=' + self.config.regions + '&markets=h2h&oddsFormat=decimal&dateFormat=iso'
        with self.repo.connection() as con:
            row = con.execute('SELECT payload FROM odds_requests WHERE endpoint=? AND retrieved_at>=? ORDER BY retrieved_at DESC LIMIT 1',
                (identity, iso(now_utc() - timedelta(seconds=self.config.request_cache_seconds)))).fetchone()
        if row:
            meta = json.loads(row[0])
            if meta['status']!=200 or not meta.get('schema_valid',True):
                raise OddsUnavailable('Bookmakerproviderns senaste försök misslyckades. Väntar till nästa kontrollerade försök.')
            return self._decode(self.repo.read_raw(meta['raw_reference']), event_id), meta
        if not self.config.api_key:
            raise OddsUnavailable('ODDS_API_KEY saknas. Bookmakerkonsensus är inte aktiverad.')
        # httpx INFO includes URLs; v4 requires query-string authentication.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        for attempt in range(2):
            started = now_utc()
            meta = {'id': uuid4().hex, 'provider': 'the-odds-api', 'endpoint': identity,
                'requested_at': iso(started), 'league': league, 'provider_event_id': event_id}
            status, content, headers = 0, b'', {}
            try:
                params = {'apiKey': self.config.api_key, 'regions': self.config.regions, 'markets': 'h2h', 'oddsFormat': 'decimal', 'dateFormat': 'iso'}
                if self.client:
                    response = self.client.get(endpoint, params=params)
                else:
                    with httpx.Client(timeout=self.config.timeout, follow_redirects=False) as client:
                        response = client.get(endpoint, params=params)
                status, content, headers = response.status_code, response.content, response.headers
            except httpx.HTTPError:
                pass  # Never log URL-bearing provider exceptions.
            retrieved = now_utc()
            redacted = self.config.api_key.encode() in content
            content = content.replace(self.config.api_key.encode(), b'[REDACTED]')
            raw = self.repo.save_raw(content) if content else None
            try:
                events = self._decode(content, event_id) if status == 200 else []
                valid_json = True
            except OddsUnavailable:
                events, valid_json = [], False
            meta.update({'retrieved_at': iso(retrieved), 'status': status, 'raw_reference': raw,
                'events_returned': len(events), 'credential_redacted': redacted,'schema_valid':valid_json,
                'quota': {k: headers.get(k) for k in ('x-requests-remaining', 'x-requests-used', 'x-requests-last')}})
            with self.repo.connection() as con:
                con.execute('INSERT INTO odds_requests VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (meta['id'], meta['provider'], identity, meta['requested_at'], meta['retrieved_at'], league, event_id, status, raw, len(events), json.dumps(meta)))
            if status == 200 and valid_json:
                return events, meta
            if status in (0, 429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(2)
                continue
            raise OddsUnavailable(f'Bookmakeroddsen kunde inte uppdateras (HTTP {status or "anslutningsfel"}).')

    @staticmethod
    def _decode(content, event_id=None):
        try:
            data = json.loads(content)
            if event_id:
                if not isinstance(data, dict) or data.get('id') != event_id:
                    raise ValueError()
                data = [data]
            if not isinstance(data, list) or any(not isinstance(e, dict) for e in data):
                raise ValueError()
            return data
        except (ValueError, UnicodeError):
            raise OddsUnavailable('Bookmakerprovidern returnerade ett oväntat schema.') from None
