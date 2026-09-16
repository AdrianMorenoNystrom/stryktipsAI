CREATE TABLE IF NOT EXISTS provider_raw_blobs(id TEXT PRIMARY KEY, content BYTEA NOT NULL, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS odds_requests(id TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL, requested_at TIMESTAMPTZ NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, league TEXT NOT NULL, event_id TEXT, status INTEGER NOT NULL, raw_reference TEXT, events_returned INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS odds_request_time ON odds_requests(league,retrieved_at);
CREATE TABLE IF NOT EXISTS consensus_snapshots(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, fixture_key TEXT NOT NULL, provider_event_id TEXT NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, source_updated_at TIMESTAMPTZ NOT NULL, eligible INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS consensus_match_time ON consensus_snapshots(draw_number,number,recorded_at);
CREATE TABLE IF NOT EXISTS bookmaker_observations(snapshot_id TEXT NOT NULL, bookmaker TEXT NOT NULL, source_updated_at TIMESTAMPTZ NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(snapshot_id,bookmaker));
CREATE TABLE IF NOT EXISTS collection_runs(id TEXT PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL, completed_at TIMESTAMPTZ, draw_number INTEGER, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS collection_time ON collection_runs(started_at);
CREATE TABLE IF NOT EXISTS collection_leases(name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL);
