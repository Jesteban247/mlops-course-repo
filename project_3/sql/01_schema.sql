CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS raw.batches (
    group_number integer NOT NULL, batch_number integer NOT NULL,
    run_id text NOT NULL UNIQUE, received_at timestamptz NOT NULL DEFAULT now(),
    row_count integer NOT NULL, status text NOT NULL DEFAULT 'received',
    received_columns jsonb, valid_rows integer, rejected_rows integer, duplicate_rows integer, quality jsonb,
    PRIMARY KEY(group_number, batch_number)
);
CREATE TABLE IF NOT EXISTS raw.properties (
    id bigserial PRIMARY KEY, group_number integer NOT NULL, batch_number integer NOT NULL,
    row_number integer NOT NULL, payload jsonb NOT NULL,
    UNIQUE(group_number, batch_number, row_number),
    FOREIGN KEY(group_number, batch_number) REFERENCES raw.batches(group_number, batch_number)
);
CREATE TABLE IF NOT EXISTS clean.properties (
    raw_id bigint PRIMARY KEY REFERENCES raw.properties(id),
    group_number integer NOT NULL, batch_number integer NOT NULL,
    property_key text NOT NULL, split text NOT NULL CHECK (split IN ('train', 'validation', 'test')),
    price double precision NOT NULL CHECK (price > 0), content_hash text NOT NULL, features jsonb NOT NULL,
    UNIQUE(group_number, content_hash)
);
CREATE INDEX IF NOT EXISTS clean_properties_split ON clean.properties(group_number, split);
CREATE TABLE IF NOT EXISTS audit.batch_decisions (
    group_number integer NOT NULL, batch_number integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), valid_rows integer NOT NULL,
    pending_rows integer NOT NULL, decision text NOT NULL, reason text NOT NULL,
    model_version text, candidate_mae double precision, champion_mae double precision,
    promotion text, run_id text, metrics jsonb, PRIMARY KEY(group_number, batch_number)
);
CREATE TABLE IF NOT EXISTS audit.training_events (
    id bigserial PRIMARY KEY, group_number integer NOT NULL, batch_number integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), mlflow_run_id text NOT NULL,
    model_version text, candidate_mae double precision, champion_mae double precision,
    promoted boolean NOT NULL, reason text NOT NULL,
    UNIQUE(group_number, batch_number)
);
CREATE TABLE IF NOT EXISTS audit.inference_events (
    id bigserial PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
    request_id text NOT NULL, payload jsonb, prediction double precision,
    model_version text, pod text, status text NOT NULL, error text
);
