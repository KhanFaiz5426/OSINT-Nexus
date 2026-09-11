import os
import re

file_path = "DESKTOP_MIGRATION_SPEC.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the broken section
broken_section_start = content.find("                      [Phase 5] Workspace File Architecture (.osint API lifecycle)\n- **Task 3.3 (Readers):**")
if broken_section_start != -1:
    correct_text = """                      [Phase 5] Workspace File Architecture (.osint API lifecycle)
                                 |
                                 v
                      [Phase 6] Desktop Shell Integration (pywebview/Electron)
                                 |
                                 v
                      [Phase 7] Application Packaging (PyInstaller)
                                 |
                                 v
                      [Phase 8] Final Verification & E2E
```

---

## 10. Phase Breakdown & Detailed Tasks

### Phase 1: Architecture Prototyping & Benchmarks
- **Objective:** Mitigate the highest risks (ADR 1, ADR 2, ADR 5) via isolated PoCs before touching application code.
- **Why Grouped:** These form the "Approval Gate." No architectural migration should begin until these prove viable.
- **Complexity/Risk:** High.
- **Task 1.1 (Graph Benchmark):** Write a standalone Python script generating a 10k node/30k edge SQLite dataset. Implement Recursive CTEs for pathfinding logic natively in SQLite. Measure load/query times to validate < 500ms multi-hop query target.
- **Task 1.2 (Storage Benchmark):** Write an `aiosqlite` script inserting 100 concurrent complex JSONB payloads into a SQLite WAL database with `busy_timeout`. Ensure no lock contention.
- **Task 1.3 (Desktop PoC):** Create a skeleton `pywebview` app that spawns a dummy FastAPI server on an ephemeral localhost port and successfully shuts it down on close.
- **Acceptance Criteria:** All benchmarks meet the targets defined in Section 7. Results formally documented.

*(Approval Gate: Do not proceed to Phase 2 until Phase 1 is signed off)*

### Phase 2: Core Storage Migration
- **Objective:** Port the PostgreSQL `asyncpg` backend to `aiosqlite`.
- **Why Grouped:** Modifies the core persistence layer affecting all other data operations. High data-integrity risk.
- **Dependencies:** Phase 1.
- **Task 2.1 (Schema):** Rewrite PostgreSQL Alembic/SQL schema to SQLite syntax. Implement `metadata` table for versioning.
- **Task 2.2 (Connection Pool):** Rewrite `app/db/client.py` to use `aiosqlite`. Implement a dynamic connection manager that binds to a specific `database_path`.
- **Task 2.3 (Queries):** Refactor all CRUD queries in `app/db/` to replace `->>` JSON operators with `json_extract()` and UUIDs with strings.
- **Affected Modules:** `app/db/*`, `alembic/*`.
- **Tests:** Database integrity tests; schema creation; JSON serialization validation.

### Phase 3: Graph Engine Migration
- **Objective:** Replace Neo4j Cypher queries with local graph traversals using SQLite.
- **Why Grouped:** Isolated, complex algorithmic work replacing a dedicated database technology.
- **Dependencies:** Phase 2.
- **Task 3.1 (Schema Updates):** Add `entities` and `relationships` tables to the SQLite schema.
- **Task 3.2 (Writers):** Rewrite `app/graph/writer.py` to insert extracted nodes and edges into SQLite instead of Neo4j.
- **Task 3.3 (Readers):**"""
    
    end_index = broken_section_start + len("                      [Phase 5] Workspace File Architecture (.osint API lifecycle)\n- **Task 3.3 (Readers):**")
    content = content[:broken_section_start] + correct_text + content[end_index - len("- **Task 3.3 (Readers):**"):]
    
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed")
