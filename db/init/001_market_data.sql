CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS market_refresh_runs (
  id UUID PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  target_trade_date DATE,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS market_runtime_snapshots (
  dataset TEXT PRIMARY KEY,
  as_of DATE NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  refresh_id UUID REFERENCES market_refresh_runs(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_runtime_snapshots_as_of_idx
  ON market_runtime_snapshots (as_of DESC);

CREATE TABLE IF NOT EXISTS market_fear_greed_daily (
  trade_date DATE PRIMARY KEY,
  score_qvix NUMERIC NOT NULL,
  score_strength NUMERIC NOT NULL,
  score_futures NUMERIC NOT NULL,
  score_volume NUMERIC NOT NULL,
  score_safety NUMERIC NOT NULL,
  our_index NUMERIC NOT NULL,
  our_zone TEXT NOT NULL,
  shanghai_index NUMERIC NOT NULL,
  raw_qvix NUMERIC NOT NULL,
  raw_strength NUMERIC NOT NULL,
  raw_futures NUMERIC NOT NULL,
  raw_volume NUMERIC NOT NULL,
  raw_safety NUMERIC NOT NULL,
  refresh_id UUID REFERENCES market_refresh_runs(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_fear_greed_daily_date_idx
  ON market_fear_greed_daily (trade_date DESC);

CREATE TABLE IF NOT EXISTS tushare_raw_cache (
  cache_key TEXT PRIMARY KEY,
  source_path TEXT NOT NULL UNIQUE,
  source_name TEXT NOT NULL,
  trade_date DATE,
  content_gzip BYTEA NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  byte_size BIGINT NOT NULL,
  refresh_id UUID REFERENCES market_refresh_runs(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tushare_raw_cache_source_trade_date_idx
  ON tushare_raw_cache (source_name, trade_date DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS market_documents (
  id UUID PRIMARY KEY,
  document_type TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  source_url TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding_model TEXT,
  embedding VECTOR,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_documents_type_idx ON market_documents (document_type);
