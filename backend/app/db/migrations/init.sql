-- OSINT Nexus — Database Schema (PostgreSQL)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Investigations
CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    target_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    depth TEXT NOT NULL DEFAULT 'standard',
    api_calls_used INT NOT NULL DEFAULT 0,
    api_budget INT NOT NULL DEFAULT 100,
    entity_count INT NOT NULL DEFAULT 0,
    relationship_count INT NOT NULL DEFAULT 0,
    observation_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_created ON investigations(created_at DESC);

-- Add count columns if they don't exist (for existing databases)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='investigations' AND column_name='entity_count') THEN
        ALTER TABLE investigations ADD COLUMN entity_count INT NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='investigations' AND column_name='relationship_count') THEN
        ALTER TABLE investigations ADD COLUMN relationship_count INT NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='investigations' AND column_name='observation_count') THEN
        ALTER TABLE investigations ADD COLUMN observation_count INT NOT NULL DEFAULT 0;
    END IF;
END $$;

-- Observations (immutable evidence records)
CREATE TABLE IF NOT EXISTS observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    source_adapter TEXT NOT NULL,
    source_version TEXT,
    collected_at TIMESTAMPTZ NOT NULL,
    method TEXT NOT NULL,
    target TEXT NOT NULL,
    raw_response JSONB NOT NULL,
    normalized_value TEXT,
    confidence FLOAT,
    status TEXT NOT NULL DEFAULT 'success',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observations_investigation ON observations(investigation_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_adapter);

-- Entities
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    source_count INT NOT NULL DEFAULT 1,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_investigation ON entities(investigation_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_value ON entities(value);

-- Investigation activity log
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_investigation ON activity_log(investigation_id);

-- Reports (generated investigation reports)
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_investigation ON reports(investigation_id);
