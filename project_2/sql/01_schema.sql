CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS audit.ingestion_batches (
 batch_id TEXT PRIMARY KEY,
 source_key TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL CHECK (status IN ('processing','completed','failed')),
 row_count INTEGER NOT NULL DEFAULT 0,
 started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS raw.encounters (
 encounter_id BIGINT PRIMARY KEY,
 patient_nbr BIGINT,
 batch_id TEXT NOT NULL,
 source_key TEXT NOT NULL,
 ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 status TEXT NOT NULL DEFAULT 'loaded',
 original JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_batch ON raw.encounters(batch_id);
CREATE TABLE IF NOT EXISTS clean.encounters (
 encounter_id BIGINT PRIMARY KEY REFERENCES raw.encounters(encounter_id),
 patient_nbr BIGINT,
 batch_id TEXT NOT NULL,
 split TEXT NOT NULL CHECK (split IN ('train','validation','test')),
 target SMALLINT NOT NULL CHECK(target IN (0,1)),
 features JSONB NOT NULL,
 processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_clean_split ON clean.encounters(split);
CREATE TABLE IF NOT EXISTS audit.inference_logs (
 request_id UUID PRIMARY KEY,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 payload JSONB NOT NULL,
 prediction JSONB NOT NULL,
 model_name TEXT NOT NULL,
 model_version TEXT,
 response_ms DOUBLE PRECISION
);
