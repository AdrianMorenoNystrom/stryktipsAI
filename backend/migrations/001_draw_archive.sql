-- Initial persistent draw archive; forward-only migration.

              CREATE TABLE IF NOT EXISTS provider_raw_payloads(id TEXT PRIMARY KEY, source TEXT NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, http_status INTEGER NOT NULL, raw_path TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS raw_source_time ON provider_raw_payloads(source,retrieved_at);
              CREATE TABLE IF NOT EXISTS provider_health(id TEXT PRIMARY KEY, at TIMESTAMPTZ NOT NULL, successful INTEGER NOT NULL, source TEXT NOT NULL, issue TEXT);
              CREATE INDEX IF NOT EXISTS health_time ON provider_health(at);
              CREATE TABLE IF NOT EXISTS stryktipset_draws(draw_number INTEGER PRIMARY KEY, sales_close_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS draws_close ON stryktipset_draws(sales_close_at);
              CREATE TABLE IF NOT EXISTS stryktipset_matches(draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(draw_number,number));
              CREATE INDEX IF NOT EXISTS matches_id ON stryktipset_matches(match_id);
              CREATE TABLE IF NOT EXISTS draw_observations(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, raw_id TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS draw_observation_time ON draw_observations(draw_number,recorded_at);
              CREATE TABLE IF NOT EXISTS crowd_snapshots(id TEXT PRIMARY KEY, observation_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, source_updated_at TIMESTAMPTZ, is_pre_close_snapshot INTEGER NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS crowd_time ON crowd_snapshots(draw_number,number,recorded_at);
              CREATE TABLE IF NOT EXISTS market_snapshots(id TEXT PRIMARY KEY, observation_id TEXT, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, retrieved_at TIMESTAMPTZ NOT NULL, source_updated_at TIMESTAMPTZ, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS market_time ON market_snapshots(draw_number,number,recorded_at);
              CREATE TABLE IF NOT EXISTS prediction_snapshots(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, match_id TEXT NOT NULL, predicted_at TIMESTAMPTZ NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS predictions_time ON prediction_snapshots(draw_number,number,predicted_at);
              CREATE TABLE IF NOT EXISTS optimizer_snapshots(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL, budget REAL NOT NULL, profile TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS optimizer_time ON optimizer_snapshots(draw_number,created_at);
              CREATE TABLE IF NOT EXISTS result_observations(id TEXT PRIMARY KEY, draw_number INTEGER NOT NULL, recorded_at TIMESTAMPTZ NOT NULL, raw_id TEXT NOT NULL, completed INTEGER NOT NULL, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS match_results(result_id TEXT NOT NULL, draw_number INTEGER NOT NULL, number INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(result_id,number));
              CREATE TABLE IF NOT EXISTS draw_payouts(result_id TEXT NOT NULL, draw_number INTEGER NOT NULL, correct INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(result_id,correct));
              CREATE INDEX IF NOT EXISTS results_draw ON result_observations(draw_number,recorded_at);
            