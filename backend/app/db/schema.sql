-- OSINT Nexus SQLite Schema
-- Target: aiosqlite / SQLite WAL mode

CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    target_type TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    depth TEXT DEFAULT 'standard',
    api_calls_used INTEGER DEFAULT 0,
    api_budget INTEGER DEFAULT 100,
    entity_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    observation_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    updated_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_created ON investigations(created_at DESC);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    source_adapter TEXT NOT NULL,
    source_version TEXT,
    collected_at TEXT NOT NULL,
    method TEXT NOT NULL,
    target TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    normalized_value TEXT,
    confidence REAL,
    status TEXT DEFAULT 'success',
    created_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_observations_investigation ON observations(investigation_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_adapter);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT NOT NULL,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.0,
    first_seen TEXT,
    last_seen TEXT,
    source_count INTEGER DEFAULT 1,
    properties TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    PRIMARY KEY (id, investigation_id)
);
CREATE INDEX IF NOT EXISTS idx_entities_investigation ON entities(investigation_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_value ON entities(value);

-- Unified Graph Relationships
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    confidence REAL DEFAULT 0.0,
    evidence TEXT DEFAULT '[]',
    discovered_at TEXT,
    method TEXT,
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    PRIMARY KEY (id, investigation_id),
    FOREIGN KEY (source_id, investigation_id) REFERENCES entities(id, investigation_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id, investigation_id) REFERENCES entities(id, investigation_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_relationships_investigation ON relationships(investigation_id);

-- Optimized Bidirectional Edge Traversal Table
CREATE TABLE IF NOT EXISTS edges_bidi (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edges_bidi_from ON edges_bidi(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_bidi_to ON edges_bidi(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_bidi_inv ON edges_bidi(investigation_id);

CREATE TRIGGER IF NOT EXISTS trg_insert_relationship
AFTER INSERT ON relationships
BEGIN
    INSERT INTO edges_bidi (from_id, to_id, investigation_id) VALUES (NEW.source_id, NEW.target_id, NEW.investigation_id);
    INSERT INTO edges_bidi (from_id, to_id, investigation_id) VALUES (NEW.target_id, NEW.source_id, NEW.investigation_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_delete_relationship
AFTER DELETE ON relationships
BEGIN
    DELETE FROM edges_bidi WHERE from_id = OLD.source_id AND to_id = OLD.target_id AND investigation_id = OLD.investigation_id;
    DELETE FROM edges_bidi WHERE from_id = OLD.target_id AND to_id = OLD.source_id AND investigation_id = OLD.investigation_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_update_relationship
AFTER UPDATE ON relationships
BEGIN
    DELETE FROM edges_bidi WHERE from_id = OLD.source_id AND to_id = OLD.target_id AND investigation_id = OLD.investigation_id;
    DELETE FROM edges_bidi WHERE from_id = OLD.target_id AND to_id = OLD.source_id AND investigation_id = OLD.investigation_id;
    
    INSERT INTO edges_bidi (from_id, to_id, investigation_id) VALUES (NEW.source_id, NEW.target_id, NEW.investigation_id);
    INSERT INTO edges_bidi (from_id, to_id, investigation_id) VALUES (NEW.target_id, NEW.source_id, NEW.investigation_id);
END;

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_activity_log_investigation ON activity_log(investigation_id);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_reports_investigation ON reports(investigation_id);

CREATE TABLE IF NOT EXISTS entity_provenance (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    entity_id TEXT NOT NULL,
    observation_id TEXT NOT NULL REFERENCES observations(id) ON DELETE CASCADE,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    UNIQUE(entity_id, observation_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_provenance_entity ON entity_provenance(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_provenance_observation ON entity_provenance(observation_id);
CREATE INDEX IF NOT EXISTS idx_entity_provenance_investigation ON entity_provenance(investigation_id);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    entity_id TEXT,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    updated_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_notes_investigation ON notes(investigation_id);
CREATE INDEX IF NOT EXISTS idx_notes_entity ON notes(entity_id);

CREATE TABLE IF NOT EXISTS confidence_overrides (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    original_confidence REAL NOT NULL,
    override_confidence REAL NOT NULL,
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE INDEX IF NOT EXISTS idx_confidence_overrides_entity ON confidence_overrides(entity_id);
CREATE INDEX IF NOT EXISTS idx_confidence_overrides_investigation ON confidence_overrides(investigation_id);
