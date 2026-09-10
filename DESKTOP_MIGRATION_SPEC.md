# OSINT Nexus: Desktop Migration Specification

**Version:** 2.1 (Detailed Desktop Architecture Transition)
**Date:** 2026-09-10
**Document Type:** Technical Migration Specification

---

## 1. Executive Summary

OSINT Nexus is transitioning from a distributed containerized web service (Docker, PostgreSQL, Neo4j, Celery, Redis) into a standalone, locally executing desktop application. The application will retain its automated OSINT pipeline, AI-assisted investigation planning, and workstation-style UI, but will require zero infrastructure management from the end user.

The target experience is a double-click executable (`osint-nexus.exe` / `osint-nexus.app`) that opens directly into a native window, allowing the user to create or open portable `.osint` investigation files.

---

## 2. Product Goals & Non-Goals

### 2.1 Product Goals
- Zero-configuration launch (no Docker, no manual database setup).
- Portable investigation state via `.osint` files (save, share, continue later).
- Complete preservation of the existing OSINT correlation engine and AI planner.
- Native desktop window experience.
- Graceful degradation if offline (though live collection requires internet).

### 2.2 Non-Goals (Explicitly Out of Scope)
- Modifying or redesigning the existing React/Cytoscape UI workstation.
- Multi-user collaboration, RBAC, or team syncing.
- Cloud hosting capabilities or browser-based remote access.
- Active exploitation, vulnerability scanning, or non-OSINT features.
- Distributed task scaling across multiple machines.

---

## 3. Current Architecture & Implementation Map

The repository implements a rigid Collect → Normalize → Extract → Resolve → Correlate pipeline.

### 3.1 Subsystem Mapping
- **Frontend Layer:** React SPA (Vite). Relies heavily on Cytoscape.js for the investigation graph and TanStack query for state. Currently built to `frontend/dist/`.
- **API Layer:** FastAPI (`backend/app/main.py`). Defines endpoints in `backend/app/api/` (investigations, entities, graph, reports). Heavily relies on dependency injection.
- **Investigation Lifecycle:** Managed deterministically by `backend/app/services/orchestrator.py` (`run_investigation_loop`). It calls the AI planner for advice, but dispatches collection tasks sequentially within rounds.
- **Relational Storage:** PostgreSQL via raw `asyncpg` queries (`backend/app/db/`). Stores investigations, immutable observations (JSONB), and activity logs.
- **Graph Storage:** Neo4j via Cypher queries (`backend/app/graph/`). Stores extracted entities and relationships.
- **Background Execution:** Celery + Redis (`backend/app/tasks/run_investigation.py`). It primarily wraps the asynchronous orchestrator loop to prevent HTTP request blocking.
- **Caching & Rate Limiting:** Redis-backed (`backend/app/core/redis.py`), utilized by the collector adapter interfaces.
- **Configuration:** Handled via `.env` and `backend/app/core/settings_store.py`.

---

## 4. Technology Evaluation & Decision Records

### ADR 1: Storage Layer (PostgreSQL -> SQLite)
- **Current:** PostgreSQL 16+ via `asyncpg`.
- **Purpose:** Stores JSON evidence (observations), tracking, activity logs.
- **Decision:** **Approved.** Migrate to SQLite via `aiosqlite`.
- **Justification:** Fits the requirement for portable `.osint` files. SQLite perfectly handles the concurrent read/write scale of a single-user OSINT investigation.
- **Risks/Implications:** 
  - Raw SQL queries must be rewritten. SQLite uses `json_extract()` instead of Postgres `->>` JSONB operators.
  - `asyncpg` connection pools must be replaced with dynamic `aiosqlite` connections pointing to the active file.
- **Acceptance Criteria:** E2E data integrity tests pass; observation JSON can be reliably searched and retrieved.

### ADR 2: Graph Layer (Neo4j -> Local Graph)
- **Current:** Neo4j via official async driver.
- **Purpose:** Multi-hop graph traversal, neighbor discovery, entity resolution logic.
- **Decision:** **Requires Benchmark.** Migrate to SQLite edge tables + In-Memory NetworkX.
- **Justification:** Removing the JVM Neo4j dependency is strictly required for a lightweight desktop app. For typical OSINT graphs (<100,000 nodes), `NetworkX` is exceptionally fast in Python.
- **Risks/Implications:**
  - `app/graph/reader.py` and `writer.py` must be completely rewritten.
  - Cypher's `MATCH path = (src)-[*1..4]-(tgt)` must be implemented as a bounded BFS in Python.
- **Evidence Required:** A benchmark script proving NetworkX can load 10,000 nodes/30,000 edges from SQLite and calculate a 4-hop path in <500ms. If it fails, pure SQLite recursive CTEs will be evaluated.

### ADR 3: Background Execution (Celery/Redis -> Local Asyncio)
- **Current:** Celery worker orchestrated via Redis.
- **Purpose:** Prevents API timeouts during long-running investigations.
- **Decision:** **Approved.** Migrate to local `asyncio` task execution inside the FastAPI process.
- **Justification:** The current `orchestrator.py` is already an `async` loop. Celery merely provides a background boundary. A simple `asyncio.create_task` or a lightweight `BackgroundTasks` queue is fully sufficient for a local application. 
- **Risks/Implications:**
  - Need to ensure long-running tasks don't block UI event loops or SSE (Server-Sent Events) streams.
  - In-process crash means the investigation terminates abruptly, requiring graceful save-state logic.

### ADR 4: Caching & Rate Limiting (Redis -> In-Process)
- **Current:** Redis.
- **Decision:** **Approved.** Migrate to Python `cachetools` (TTL Cache) and `aiolimiter`.
- **Justification:** Solves the Redis dependency. Limits are applied per API key / OSINT source, easily handled in memory.

### ADR 5: Desktop Shell Architecture
- **Decision:** **Approved.** Use `pywebview`.
- **Justification:** `pywebview` creates a native OS window utilizing Edge Chromium (Windows) or WebKit (Mac). It is entirely Python-native, requiring no Rust (like Tauri) or heavy Chromium bundles (like Electron), minimizing the packaging complexity of the Python backend.
- **Architecture:** 
  1. User launches `osint-nexus.exe`.
  2. Bootstrapper finds a free local port.
  3. Bootstrapper spawns `uvicorn` (FastAPI) on that port in a daemon thread.
  4. Bootstrapper opens `pywebview` window pointing to `http://localhost:port`.
  5. Upon window close, the FastAPI thread is gracefully terminated.

---

## 5. Investigation File Specification (`.osint`)

The `.osint` file is the fundamental unit of the new architecture. It is a standard **SQLite3 database file**.

### 5.1 Internal Schema
- `metadata`: Schema version, investigation name, creation date, status.
- `observations`: The immutable evidence logs (target, source, raw JSON response, method, timestamp).
- `entities`: Normalized extracted intelligence (id, type, value, properties).
- `relationships`: Graph edges (source_id, target_id, type, confidence, evidence_ids).
- `activity_log`: Audit trail of the investigation loop (AI plans, user actions).

### 5.2 Atomic Operations & Recovery
- File operations (Save, Export) utilize WAL (Write-Ahead Logging) mode to prevent corruption if the app crashes during API collection.
- The app will automatically sync state to the active `.osint` file upon every completed orchestrator round.

### 5.3 Secrets Separation
- **CRITICAL:** API keys (OpenAI, GitHub, Shodan, etc.) must **never** be saved into the `.osint` file. 
- Configuration and API keys will live in `~/.osint-nexus/config.json` (or OS credential manager) globally on the user's machine.

---

## 6. Security Architecture

- **Authentication:** Removed. Since this is a local desktop application bound to `127.0.0.1`, traditional JWT/user auth is unnecessary overhead.
- **API Security:** The local API must only bind to `127.0.0.1` / `localhost` to prevent network exposure.
- **SSRF Protection:** The existing `security.py` preventing internal network scanning remains strictly enforced to prevent maliciously crafted `.osint` targets from triggering local network scans.
- **File Parsing:** SQLite pragmas must be used to ensure safely opening `.osint` files imported from unknown sources (preventing malicious SQL triggers).

---

## 7. Scalability & Performance Requirements

We define investigation sizes based on the entity count generated by OSINT correlation:
- **Small:** 10–50 entities (Rapid target check).
- **Medium:** 100–500 entities (Standard AI pivot depth).
- **Large:** 1,000–10,000 entities (Deep infrastructure analysis).

**Performance Targets:**
- App startup time: < 3 seconds.
- `.osint` file load time (Large): < 2 seconds.
- Cytoscape UI render (1,000 nodes): < 1.5 seconds.
- Graph pathfinding (4 hops, Large graph): < 500ms.
- API limits: Maximum 5 concurrent external OSINT API requests at any given time (enforced by `aiolimiter`).

---

## 8. Migration Dependency Graph

```
[Phase 1] Architecture Benchmarking (NetworkX / SQLite)
       |
       v
[Phase 2] Storage Migration (asyncpg -> aiosqlite)
       |
       +------------------------------------+
       |                                    |
       v                                    v
[Phase 3] Graph Migration            [Phase 4] Background Workers
(Neo4j -> NetworkX)                  (Celery -> asyncio)
       |                                    |
       +------------------------------------+
       |
       v
[Phase 5] Workspace Management (File API)
       |
       v
[Phase 6] Desktop Shell Integration (pywebview)
       |
       v
[Phase 7] Packaging & Distribution (PyInstaller)
       |
       v
[Phase 8] Final Verification
```

---

## 9. Detailed Phase Breakdown

### Phase 1: Architecture Benchmarking & Validation
- **Objective:** Prove that NetworkX and SQLite can handle OSINT-scale graphs efficiently before committing to the architecture.
- **Complexity:** Low. **Risk:** High (Decision blocks Phase 3).
- **Tasks:**
  1. Write a standalone Python script generating a SQLite database with 10,000 nodes and 30,000 edges.
  2. Implement the `get_multi_hop_paths` algorithm using `NetworkX`.
  3. Measure execution time and memory overhead.
- **Acceptance Criteria:** 4-hop path query returns in < 500ms.
- **Outcome Status:** *Requires Benchmark.*

### Phase 2: Core Storage Migration
- **Objective:** Port the PostgreSQL backend to SQLite.
- **Why Separate Phase:** Highest data-integrity risk. 
- **Tasks:**
  1. Replace `asyncpg` with `aiosqlite` in `app/db/client.py`.
  2. Rewrite `init.sql` / Alembic schemas for SQLite (handling `JSON` extensions).
  3. Refactor CRUD queries to use SQLite JSON functions.
  4. Establish dynamic DB connection patterns based on active file.
- **Affected Modules:** `app/db/*`, `alembic/*`.
- **Tests:** Data consistency tests, JSON read/write validation.

### Phase 3: Graph Engine Migration
- **Objective:** Replace Neo4j with NetworkX.
- **Why Separate Phase:** Replaces the core relationship discovery logic.
- **Dependencies:** Phase 1, Phase 2.
- **Tasks:**
  1. Add `relationships` table to SQLite schema.
  2. Rewrite `app/graph/writer.py` to insert edges into SQLite.
  3. Rewrite `app/graph/reader.py` to load edges into `NetworkX` and execute BFS traversal.
  4. Ensure output maps perfectly to the Cytoscape format `{"nodes": [], "edges": []}`.
- **Affected Modules:** `app/graph/*`.
- **Tests:** Unit tests comparing old Cypher logic vs new NetworkX logic for neighbor discovery.

### Phase 4: Execution Engine Migration
- **Objective:** Eliminate Celery and Redis.
- **Tasks:**
  1. Remove Celery initialization from `app/tasks/celery_app.py`.
  2. Modify `app/api/investigations.py` to trigger `run_investigation_loop` via `asyncio.create_task()` (or similar queue manager).
  3. Implement `cachetools` TTLCache in `app/collectors/cache.py`.
  4. Implement `aiolimiter` in OSINT collector adapters.
- **Affected Modules:** `app/tasks/*`, `app/core/redis.py`, `app/api/investigations.py`.
- **Tests:** Concurrency stress tests.

### Phase 5: Workspace File API
- **Objective:** Introduce the `.osint` file model to the application state.
- **Tasks:**
  1. Create `/api/v1/workspace/new`, `open`, `close` endpoints.
  2. Implement backend state locking (only one investigation open at a time).
  3. Update React frontend to show "Welcome" screen, allowing file selection.
- **Affected Modules:** `app/api/workspace.py`, `frontend/src/App.tsx`.

### Phase 6: Desktop Shell Integration
- **Objective:** Provide a native application window.
- **Tasks:**
  1. Implement `launcher.py` using `pywebview`.
  2. Start `uvicorn` on a dynamic port in a daemon thread.
  3. Mount React `dist/` directory as static files in FastAPI.
  4. Bind OS native Open/Save dialogs to trigger workspace endpoints.
- **Affected Modules:** `launcher.py`, `app/main.py`.

### Phase 7: Packaging & Distribution
- **Objective:** Generate a standalone installer/executable.
- **Tasks:**
  1. Write `build.py` utilizing PyInstaller.
  2. Ensure `aiosqlite`, `NetworkX`, and React static files are correctly embedded in the `.spec` bundle.
- **Affected Modules:** `build.py`, `osint-nexus.spec`.

---

## 10. Final Verification Plan

The completed application must pass:
1. **Migration Integrity:** Importing an old investigation JSON export into the new SQLite format preserves all nodes, edges, and provenance data.
2. **Crash/Recovery:** Force-killing the `.exe` during a running investigation correctly preserves the investigation state up to the last completed round.
3. **Packaging:** The compiled executable launches cleanly on a fresh Windows sandbox without Python installed.
4. **Performance:** Loading a synthetic `.osint` file with 5,000 entities visualizes in the React frontend within 3 seconds, without crashing the internal FastAPI thread.
5. **Security:** The backend correctly rejects target URLs resolving to `127.0.0.1` or `192.168.x.x`.
