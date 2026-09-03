# TASKS

## OSINT Nexus: Project Task Breakdown

**Version:** 1.0  
**Date:** 2026-09-03  
**Based on:** PROJECT_SPECIFICATION.md, TECH_STACK.md

---

## Overview

This document breaks the OSINT Nexus project into **9 phases** with concrete tasks. Each task has a clear output and dependency. Total estimated effort: **8–12 weeks** for a 2–3 person student team working part-time.

---

## Phase 1 — Project Scaffolding & Architecture

**Goal:** Runnable skeleton with all components stubbed; databases running; basic API responding.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 1.1 | Initialize Git repository with branch strategy (main + feature branches) | Repository ready | None |
| 1.2 | Create Docker Compose with PostgreSQL, Neo4j, Redis | `docker-compose.yml` with all 3 services running | None |
| 1.3 | Create FastAPI project structure (app/, api/, core/, models/, services/, collectors/, ai/, graph/, db/) | Directory skeleton | 1.1 |
| 1.4 | Define Pydantic models: Investigation, Observation, Entity, Relationship, RawResult | `models/` with validated schemas | 1.3 |
| 1.5 | Define database schema: investigations, observations, entities, activity_log tables | SQL migration scripts | 1.4 |
| 1.6 | Initialize React + Vite + TypeScript project with Tailwind CSS and shadcn/ui | Frontend skeleton | 1.1 |
| 1.7 | Create API route stubs: `/investigations`, `/entities`, `/graph`, `/reports` | FastAPI routes returning placeholder JSON | 1.3 |
| 1.8 | Connect FastAPI to PostgreSQL (async driver: asyncpg) | DB connection verified | 1.2, 1.3 |
| 1.9 | Connect FastAPI to Neo4j (neo4j Python driver) | Graph DB connection verified | 1.2, 1.3 |
| 1.10 | Connect FastAPI to Redis (redis-py) | Cache connection verified | 1.2, 1.3 |
| 1.11 | Set up Celery worker with Redis broker | Celery worker starts, can execute simple task | 1.10 |
| 1.12 | Create basic React layout: sidebar, main area, header | Dashboard shell renders | 1.6 |
| 1.13 | Create `.env.example` with all required environment variables | Documented env config | 1.3 |
| 1.14 | Set up Ruff (Python linting) + Black (formatting) + ESLint + Prettier (TS) | Linting and formatting configured | 1.1 |

**Milestone:** `docker compose up` starts all services. `curl localhost:8000/health` returns 200. Frontend renders shell.

---

## Phase 2 — Target Classification & Investigation Management

**Goal:** User can create an investigation with a target. System classifies target type.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 2.1 | Implement target classifier: regex rules for domain, IP (v4/v6), URL, email, username | `classifier.py` with tests | 1.4 |
| 2.2 | Implement input normalization: lowercase domains, strip trailing dots, validate IPs, parse URLs | `normalizer.py` (target-level) | 2.1 |
| 2.3 | Create `POST /investigations` endpoint: accepts target + name + depth, classifies, stores | API endpoint functional | 1.7, 2.1 |
| 2.4 | Create `GET /investigations` endpoint: list all investigations | API endpoint functional | 1.8 |
| 2.5 | Create `GET /investigations/{id}` endpoint: return investigation details | API endpoint functional | 1.8 |
| 2.6 | Create `POST /investigations/{id}/stop` endpoint: mark investigation as stopped | API endpoint functional | 1.8 |
| 2.7 | Frontend: "New Investigation" form (target input, name, depth selector) | Form component | 1.12 |
| 2.8 | Frontend: Investigations list page with table (TanStack Table) | List page functional | 1.12, 1.8 |
| 2.9 | Write unit tests for classifier and normalizer | Test suite passes | 2.1, 2.2 |

**Milestone:** User can create an investigation via API or UI. Target is classified. Investigation appears in list.

---

## Phase 3 — OSINT Collectors

**Goal:** System can collect data from DNS, WHOIS, CT, GitHub, HTTP, and threat intelligence sources.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 3.1 | Define `OSINTCollector` protocol and `RawResult` schema | `collectors/base.py` | 1.4 |
| 3.2 | Implement Redis-based cache layer for collector responses | `collectors/cache.py` | 1.10 |
| 3.3 | Implement per-collector rate limiter (token bucket) | `collectors/rate_limiter.py` | 1.10 |
| 3.4 | Implement retry logic with exponential backoff | `collectors/retry.py` | None |
| 3.5 | DNS collector: query A, AAAA, MX, NS, TXT, SOA, CAA records via `dnspython` | `dns_collector.py` + tests | 3.1 |
| 3.6 | WHOIS/RDAP collector: query domain registration data via `python-whois` or RDAP API | `whois_collector.py` + tests | 3.1 |
| 3.7 | Certificate Transparency collector: query crt.sh API for certificate data | `ct_collector.py` + tests | 3.1 |
| 3.8 | IP-to-ASN collector: query Team Cymru or RIPEstat for ASN mapping | `ip_asn_collector.py` + tests | 3.1 |
| 3.9 | GitHub collector: query GitHub API for user profiles, repositories, commits | `github_collector.py` + tests | 3.1 |
| 3.10 | HTTP collector: perform HEAD/GET requests, capture headers, title, redirects, technologies | `http_collector.py` + tests | 3.1 |
| 3.11 | Threat intelligence collector: query AbuseIPDB API, URLhaus API | `threat_intel_collector.py` + tests | 3.1 |
| 3.12 | Create collector registry: auto-discover and register all collectors | `collectors/registry.py` | 3.5–3.11 |
| 3.13 | Implement Celery tasks for each collector (async dispatch) | `tasks/collect_*.py` | 3.12, 1.11 |
| 3.14 | Implement raw observation storage (PostgreSQL `observations` table) | Observation CRUD | 1.8 |
| 3.15 | API key management: load from env vars; disable collectors if key missing | `core/config.py` updates | 3.1 |

**Milestone:** Each collector can be called independently and returns a `RawResult`. Results are cached. Rate limits enforced. Raw observations stored.

---

## Phase 4 — Normalization, Extraction & Resolution

**Goal:** Raw collector output is transformed into normalized entities and relationships.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 4.1 | Implement IP normalizer: canonical format, leading zero removal, IPv4/IPv6 standardization | `normalizer.py` (IP functions) | 3.14 |
| 4.2 | Implement domain normalizer: lowercase, trailing dot removal, punycode decode | `normalizer.py` (domain functions) | 3.14 |
| 4.3 | Implement email normalizer: lowercase, syntax validation | `normalizer.py` (email functions) | 3.14 |
| 4.4 | Implement timestamp normalizer: convert all formats to ISO 8601 UTC | `normalizer.py` (time functions) | 3.14 |
| 4.5 | Implement entity extractor: regex patterns for domain, IP, email, ASN, URL, technology | `extractor.py` | 4.1–4.4 |
| 4.6 | Implement entity extractor: parse DNS responses into entity objects | `extractor.py` (DNS) | 4.5 |
| 4.7 | Implement entity extractor: parse WHOIS responses into entity objects | `extractor.py` (WHOIS) | 4.5 |
| 4.8 | Implement entity extractor: parse CT responses into entity objects | `extractor.py` (CT) | 4.5 |
| 4.9 | Implement entity resolver: exact match deduplication | `resolver.py` (exact) | 4.5 |
| 4.10 | Implement entity resolver: normalized match deduplication | `resolver.py` (normalized) | 4.9 |
| 4.11 | Implement entity resolver: co-occurrence detection (entities appearing together) | `resolver.py` (co-occurrence) | 4.9 |
| 4.12 | Implement relationship detector: extract relationships from normalized data (hosted_on, uses_ns, etc.) | `relationship_detector.py` | 4.6–4.8 |
| 4.13 | Implement confidence scorer: source reliability × data quality × corroboration × recency | `confidence.py` | 4.12 |
| 4.14 | Write unit tests for all normalizers, extractors, resolvers, relationship detector | Test suite passes | 4.1–4.13 |

**Milestone:** Raw observation → normalized data → extracted entities → resolved entities → detected relationships → confidence scores. All deterministic, no AI involved. (AI-assisted entity matching is advisory-only and implemented in Phase 6 as part of the AI layer.)

---

## Phase 5 — Knowledge Graph & Correlation

**Goal:** Entities and relationships are stored in Neo4j. Graph queries work. Graph API exposes data to frontend.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 5.1 | Define Neo4j node labels and relationship types matching entity/relationship models | Cypher constraints | 1.9 |
| 5.2 | Implement graph writer: create/update nodes in Neo4j from entity list | `graph/writer.py` | 5.1 |
| 5.3 | Implement graph writer: create/update edges from relationship list | `graph/writer.py` (edges) | 5.2 |
| 5.4 | Implement graph reader: query subgraph for an investigation (all entities + relationships) | `graph/reader.py` | 5.1 |
| 5.5 | Implement graph reader: query neighbors of a specific entity | `graph/reader.py` (neighbors) | 5.4 |
| 5.6 | Implement graph reader: query multi-hop paths between entities | `graph/reader.py` (paths) | 5.4 |
| 5.7 | Implement correlation engine: orchestrate normalize → extract → resolve → detect → write to graph | `services/correlator.py` | 4.14, 5.2, 5.3 |
| 5.8 | API: `GET /investigations/{id}/graph` — return nodes + edges for Cytoscape.js | Graph endpoint | 5.4 |
| 5.9 | API: `GET /entities/{id}` — return entity details + evidence + neighbors | Entity endpoint | 5.5 |
| 5.10 | API: `GET /entities/{id}/evidence` — return all observations for entity | Evidence endpoint | 1.14 |
| 5.11 | Write integration tests: create investigation → collect → correlate → verify graph | Integration test | 5.7 |

**Milestone:** End-to-end: investigation created → collectors run → data normalized → graph populated. Graph API returns Cytoscape.js-compatible JSON.

---

## Phase 6 — Investigation Orchestrator & AI Planner

**Goal:** Automated investigation loop with AI-assisted pivot planning.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 6.1 | Implement orchestrator: dispatch initial collectors based on target type | `services/orchestrator.py` | 2.1, 3.13 |
| 6.2 | Implement orchestrator: collect → normalize → extract → resolve → correlate pipeline | `services/orchestrator.py` (pipeline) | 5.7 |
| 6.3 | Implement orchestrator: budget tracking (API call counter per investigation) | Budget enforcement | 6.1 |
| 6.4 | Implement orchestrator: depth tracking (max pivot rounds) | Depth enforcement | 6.1 |
| 6.5 | Implement orchestrator: stopping conditions (no new entities, budget exhausted, depth reached) | Stop detection | 6.3, 6.4 |
| 6.6 | Implement Celery task: `run_investigation` — full loop as background task | `tasks/run_investigation.py` | 6.2, 1.11 |
| 6.7 | API: `POST /investigations/{id}/start` — trigger investigation loop | Start endpoint | 6.6 |
| 6.8 | API: `GET /investigations/{id}/status` — return investigation state | Status endpoint | 6.6 |
| 6.9 | Implement AI planner: prompt LLM with graph state, get pivot recommendations with reasoning | `ai/planner.py` | 5.4, 1.11 |
| 6.10 | Implement AI planner: structured JSON output parsing and validation | `ai/planner.py` (parser) | 6.9 |
| 6.11 | Implement AI analyzer: summarize findings, risk assessment, key findings | `ai/analyzer.py` | 5.4 |
| 6.12 | Implement pivot selection: filter AI recommendations by budget and rate limits | `services/pivot_selector.py` | 6.9, 6.3, 3.3 |
| 6.13 | Implement hallucination prevention: validate AI-referenced observation IDs exist in DB | `ai/validator.py` | 6.10, 1.14 |
| 6.14 | API: `GET /investigations/{id}/ai-analysis` — return AI summary + recommendations | AI endpoint | 6.11 |
| 6.15 | Write tests: orchestrator loop with mocked collectors and mocked AI | Integration tests | 6.6, 6.9 |

**Milestone:** User clicks "Start Investigation." System runs full loop: collect → process → AI plans → pivot → collect → process → ... → stop. Budget and depth enforced.

---

## Phase 7 — Frontend Dashboard

**Goal:** Investigator can create, view, and interact with investigations via web UI.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 7.1 | Set up TanStack Query hooks for API calls (investigations, entities, graph) | `hooks/` | 1.6, 1.7 |
| 7.2 | Set up Zustand store for investigation state (selected entity, filters, etc.) | `store/` | 1.6 |
| 7.3 | Implement Investigation Detail page: overview panel, status, target, stats | Detail page | 2.8 |
| 7.4 | Implement Entity List panel: filterable, sortable table of all entities (TanStack Table) | Entity list | 5.9 |
| 7.5 | Implement Entity Detail panel: entity properties, evidence list, connected entities | Entity detail | 5.9, 5.10 |
| 7.6 | Implement Knowledge Graph view: Cytoscape.js integration, zoom, pan, filter | Graph view | 5.8 |
| 7.7 | Implement graph interaction: click node → navigate to entity detail | Graph click | 7.5, 7.6 |
| 7.8 | Implement Timeline panel: chronological event list from activity log | Timeline | 1.14 |
| 7.9 | Implement Evidence panel: expandable raw data for selected entity/relationship | Evidence panel | 5.10 |
| 7.10 | Implement AI Analysis panel: display AI summary, risk, findings, recommended pivots | AI panel | 6.14 |
| 7.11 | Implement Activity Log panel: real-time event stream during investigation | Activity log | 1.14 |
| 7.12 | Implement "Start Investigation" button and progress indicator | Start action | 6.7 |
| 7.13 | Implement "Export Report" button (triggers report generation) | Export action | 8.x |
| 7.14 | Implement filter/search: entity type filter, confidence range, date range | Filters | 7.4 |
| 7.15 | Implement responsive layout: panels resize, graph fills available space | Layout | 7.1–7.14 |

**Milestone:** Investigator opens dashboard, creates investigation, watches real-time progress, views graph, clicks entities, sees evidence, reads AI analysis.

---

## Phase 8 — Reporting

**Goal:** System generates evidence-backed investigation reports.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 8.1 | Implement report data collector: aggregate all entities, relationships, observations, AI analysis | `services/report_data.py` | 5.7, 6.11 |
| 8.2 | Create Jinja2 HTML report template: executive summary, findings, graph image, evidence table, methodology | `templates/report.html` | 8.1 |
| 8.3 | Implement HTML report generator: render template with investigation data | `services/report_generator.py` (HTML) | 8.2 |
| 8.4 | Implement PDF report generator: HTML → PDF via WeasyPrint | `services/report_generator.py` (PDF) | 8.3 |
| 8.5 | Implement JSON report generator: structured export of all data | `services/report_generator.py` (JSON) | 8.1 |
| 8.6 | Implement CSV export: entity list and observation list | `services/report_generator.py` (CSV) | 8.1 |
| 8.7 | API: `POST /investigations/{id}/reports` — trigger report generation | Report endpoint | 8.3–8.6 |
| 8.8 | API: `GET /investigations/{id}/reports/{report_id}` — download report | Download endpoint | 8.7 |
| 8.9 | Frontend: Reports page with generation button, preview, download links | Reports page | 8.7, 8.8 |
| 8.10 | Write tests: report generation with sample investigation data | Test suite | 8.3–8.6 |

**Milestone:** After investigation completes, user can generate HTML/PDF/JSON/CSV reports with full evidence attribution.

---

## Phase 9 — Testing, Polish & Documentation

**Goal:** Production-ready system with comprehensive tests and documentation.

| Task | Description | Output | Dependency |
|---|---|---|---|
| 9.1 | Write unit tests for normalizer, extractor, resolver, confidence scorer | Backend unit tests | 4.14 |
| 9.2 | Write integration tests: full investigation flow with mocked collectors | Integration tests | 6.15 |
| 9.3 | Write collector tests: each collector against recorded API responses (no live calls in CI) | Collector tests | 3.5–3.11 |
| 9.4 | Write API contract tests: validate all endpoints return expected schemas | API tests | 1.7 |
| 9.5 | Write frontend component tests: key components render correctly | Vitest tests | 7.1–7.15 |
| 9.6 | Write E2E test: create investigation → start → view graph → export report (Playwright) | E2E test | 7.15, 8.9 |
| 9.7 | Performance test: investigation with 50+ entities renders graph in < 2s | Performance baseline | 7.6 |
| 9.8 | Create seed data: 3 sample investigations with known ground truth | Test fixtures | 5.7 |
| 9.9 | Write README.md: project description, setup, usage, architecture | Documentation | All |
| 9.10 | Write API documentation: verify OpenAPI spec is complete and accurate | API docs | 1.7 |
| 9.11 | Security audit: verify no secrets in code, CORS configured, input validated | Security review | All |
| 9.12 | Set up GitHub Actions CI: lint → test → build on push | CI pipeline | 1.14 |

**Milestone:** All tests pass. CI pipeline runs. Documentation complete. System is demo-ready.

---

## Dependency Graph

```
Phase 1 (Scaffolding)
  │
  ├── Phase 2 (Classification & Investigation Management)
  │     │
  │     ├── Phase 3 (OSINT Collectors)
  │     │     │
  │     │     └── Phase 4 (Normalization, Extraction, Resolution)
  │     │           │
  │     │           └── Phase 5 (Knowledge Graph & Correlation)
  │     │                 │
  │     │                 └── Phase 6 (Orchestrator & AI Planner)
  │     │                       │
  │     │                       ├── Phase 7 (Frontend Dashboard)
  │     │                       │     │
  │     │                       │     └── Phase 9 (Testing & Polish)
  │     │                       │
  │     │                       └── Phase 8 (Reporting)
  │     │                             │
  │     │                             └── Phase 9 (Testing & Polish)
```

---

## Task Summary by Phase

| Phase | Tasks | Key Output |
|---|---|---|
| 1. Scaffolding | 14 | Docker Compose, FastAPI skeleton, React shell, DB connections |
| 2. Classification | 9 | Target classifier, investigation CRUD API, new investigation form |
| 3. Collectors | 15 | 7 OSINT adapters, caching, rate limiting, Celery tasks |
| 4. Normalization | 14 | Normalizers, extractors, resolvers, relationship detector, confidence scorer |
| 5. Graph | 11 | Neo4j read/write, correlation engine, graph API |
| 6. Orchestrator | 15 | Investigation loop, AI planner, pivot selection, budget/depth control |
| 7. Frontend | 15 | Dashboard, graph view, entity details, evidence panel, AI panel |
| 8. Reporting | 10 | HTML/PDF/JSON/CSV report generation |
| 9. Testing | 12 | Unit, integration, E2E tests, documentation, CI |
| **Total** | **115** | |

---

## Recommended Work Order

**Week 1–2:** Phase 1 (scaffolding) + Phase 2 (classification)  
**Week 3–4:** Phase 3 (collectors)  
**Week 5–6:** Phase 4 (normalization/extraction) + Phase 5 (graph)  
**Week 7–8:** Phase 6 (orchestrator + AI)  
**Week 9–10:** Phase 7 (frontend)  
**Week 11:** Phase 8 (reporting)  
**Week 12:** Phase 9 (testing, polish, documentation)

**Parallel tracks:** After Phase 1, frontend (Phase 7 groundwork) and backend (Phases 2–6) can proceed in parallel on separate branches.

---

## MVP Checkpoint (End of Week 8)

After Phase 6, the system should be functional as a minimal OSINT investigation tool:

- User can create a domain or IP investigation (via API)
- System collects from DNS, WHOIS, CT, HTTP, and threat intelligence
- Data is normalized, entities extracted, relationships detected
- Knowledge graph is built and queryable via API
- AI planner suggests pivots with reasoning
- Investigation loop runs with budget/depth control
- Graph API returns Cytoscape.js-compatible data

**Note:** The Phase 6 MVP is a functional backend engine with API endpoints. The full interactive dashboard (graph visualization, evidence panel, AI analysis panel) is implemented in Phase 7.

**If the MVP works, the project is a legitimate OSINT investigation framework.** Phases 7–9 add the frontend UI, reporting, and testing — but the core intelligence pipeline is complete.

---

*End of task breakdown.*
