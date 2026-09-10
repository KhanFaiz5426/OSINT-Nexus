# OSINT Nexus

**AI-Assisted OSINT Investigation and Correlation Framework**

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Capabilities](#key-capabilities)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Supported Targets and Sources](#supported-targets-and-sources)
- [AI/LLM Integration](#aillm-integration)
- [Evidence, Provenance, and Confidence](#evidence-provenance-and-confidence)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Setup and Running](#setup-and-running)
- [Testing and Quality Checks](#testing-and-quality-checks)
- [Usage Example](#usage-example)
- [API Reference](#api-reference)
- [Reports and Export](#reports-and-export)
- [Security](#security)
- [Deployment](#deployment)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Project Status](#project-status)
- [License](#license)

---

## Project Overview

OSINT Nexus is a modular, end-to-end OSINT investigation framework that automates the collection, normalization, correlation, and reporting of publicly available information. Given an investigation target (a domain, IP address, URL, email, username, or organization), the system orchestrates multi-source data collection, extracts entities and relationships, builds an interactive knowledge graph, and generates evidence-backed reports — all with full source attribution and confidence scoring.

OSINT investigations today suffer from fragmented workflows across standalone tools, manual pivot selection, and poor evidence management. OSINT Nexus addresses these problems with a unified pipeline: a single target triggers automated collection, normalization, extraction, correlation, AI-assisted analysis, and reporting within a single system.

---

## Key Capabilities

| Capability | Description |
|---|---|
| **Multi-source collection** | Automated OSINT collection from DNS, WHOIS, certificate transparency, IP/ASN, GitHub, HTTP metadata, and threat intelligence feeds |
| **Entity extraction** | Identifies domains, IPs, emails, ASNs, URLs, technologies, and other entities from raw collector responses |
| **Entity resolution** | Deduplicates entities across sources using exact and normalized-value matching |
| **Relationship detection** | Identifies hosting, registration, certificate, mail, and other relationships between entities |
| **Knowledge graph** | Interactive Neo4j-backed graph visualization with zoom, filter, and exploration |
| **AI-assisted planning** | LLM-powered pivot suggestions and investigation analysis (optional; works without LLM) |
| **Confidence scoring** | Automatic confidence scores for entities and relationships based on source reliability, data quality, and recency |
| **Evidence provenance** | Every observation records its source adapter, collection timestamp, raw response, and method |
| **Report generation** | Export investigation findings in HTML, PDF, JSON, or CSV formats with source attribution |
| **Budget control** | Configurable API call budgets and depth limits to prevent runaway investigations |

---

## How It Works

The investigation pipeline follows a deterministic collect → normalize → extract → resolve → correlate → analyze → report flow:

```
Target Input
     │
     ▼
┌─────────────────┐
│  Classification  │  Determines target type (domain, IP, URL, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Collection    │  Dispatches relevant OSINT collectors in parallel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Normalization   │  Standardizes raw data (lowercase, canonical IPs, ISO timestamps)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Extraction    │  Pulls entities (domains, IPs, emails, etc.) from responses
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Resolution    │  Deduplicates and merges entity records across sources
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Relationship    │  Detects structural relationships (hosted_on, registered_by, etc.)
│    Detection     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Correlation    │  Cross-references findings, scores confidence, builds graph
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI Analysis     │  (Optional) LLM summarizes findings, suggests next steps
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Reporting      │  Generates HTML/PDF/JSON/CSV reports with provenance
└─────────────────┘
```

The orchestrator manages the collection loop with configurable depth (shallow / standard / deep) and API budget limits. After each collection round, the AI planner may suggest additional pivot targets based on the current graph state, which the orchestrator evaluates and dispatches.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Frontend (React)                     │
│   Dashboard · Investigation Detail · Knowledge Graph   │
│   Entity List · Timeline · Reports · AI Analysis       │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP
                       ▼
┌──────────────────────────────────────────────────────┐
│               FastAPI Backend (Python)                 │
│  ┌─────────┐  ┌───────────┐  ┌───────────────────┐  │
│  │   API    │  │ Services  │  │    Collectors     │  │
│  │ Routes   │  │ Pipeline  │  │ DNS · WHOIS · CT  │  │
│  │          │  │           │  │ GitHub · HTTP ·   │  │
│  │          │  │           │  │ Threat Intel      │  │
│  └─────────┘  └───────────┘  └───────────────────┘  │
│  ┌─────────┐  ┌───────────┐  ┌───────────────────┐  │
│  │   AI    │  │  Graph    │  │    Database       │  │
│  │Planner  │  │  Reader/  │  │    Client         │  │
│  │Analyzer │  │  Writer   │  │  (asyncpg)        │  │
│  └─────────┘  └───────────┘  └───────────────────┘  │
└───────┬──────────────┬──────────────┬───────────────┘
        │              │              │
        ▼              ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│ PostgreSQL │ │   Neo4j    │ │   Redis    │
│            │ │            │ │            │
│ investig.  │ │  knowledge │ │  caching   │
│ observ.    │ │    graph   │ │  Celery    │
│ entities   │ │  entities  │ │  broker    │
│ reports    │ │  rels      │ │            │
│ activity   │ │            │ │            │
└────────────┘ └────────────┘ └────────────┘
                                        │
                                        ▼
                                 ┌────────────┐
                                 │   Celery   │
                                 │   Worker   │
                                 │ (optional) │
                                 └────────────┘
```

---

## Supported Targets and Sources

### Target Types

| Type | Examples | Classification |
|---|---|---|
| Domain | `example.com`, `sub.domain.co.uk` | Regex-based TLD matching |
| IP Address | `93.184.216.34`, `2606:2800:220:1:248:1893:25c8:1946` | IPv4/IPv6 format validation |
| URL | `https://example.com/path?q=1` | Scheme + authority parsing |
| Email | `admin@example.com` | Local@domain pattern |
| Username | `cyberresearcher42` | Fallback classifier |
| Organization | `Acme Corp` | Explicit designation |

### OSINT Source Adapters

| Collector | Source | API Key Required | What It Collects |
|---|---|---|---|
| DNS | `dnspython` | No | A, AAAA, MX, NS, TXT, SOA, CAA records |
| WHOIS | `python-whois` | No | Registrar, registrant, nameservers, dates |
| Certificate Transparency | crt.sh | No | Certificates, issuers, subdomains (SAN) |
| IP-to-ASN | Team Cymru / RIPEstat | No | ASN mapping, organization, BGP prefix |
| GitHub | GitHub API | `GITHUB_TOKEN` (optional) | User profiles, repositories, commits |
| HTTP | `httpx` | No | Headers, title, redirects, technologies |
| Threat Intelligence | AbuseIPDB / URLhaus | `ABUSEIPDB_API_KEY` (optional) | IP reputation, malicious URL lookups |

Collectors with missing API keys are automatically disabled. The investigation proceeds with available sources.

---

## AI/LLM Integration

OSINT Nexus separates deterministic processing from AI-assisted reasoning:

| Component | Role | Deterministic? |
|---|---|---|
| Classification, normalization, extraction, resolution, relationship detection | Core pipeline — always runs | Yes |
| Orchestrator (dispatch, budget, depth) | Controls flow — never delegates decisions to LLM | Yes |
| AI Planner | Suggests pivot targets based on graph state; advisory only | No (LLM) |
| AI Analyzer | Summarizes findings, assesses risk; output is not source evidence | No (LLM) |
| AI Validator | Validates LLM output against schemas, filters hallucinated references | Yes |

When no LLM provider is configured (`LLM_PROVIDER=none`), the planner returns deterministic defaults based on entity types and the analyzer returns a stub summary. The core investigation pipeline works fully without any LLM.

### Supported Providers

| Provider | `LLM_PROVIDER` | API Key | Cost | Notes |
|---|---|---|---|---|
| NVIDIA NIM | `nvidia` | `LLM_API_KEY` | Free tier available | Primary hosted provider. Sign up at [build.nvidia.com](https://build.nvidia.com/) |
| OpenAI | `openai` | `LLM_API_KEY` | Paid | GPT-4o and other models |
| Anthropic | `anthropic` | `LLM_API_KEY` | Paid | Claude models |
| Ollama | `ollama` | None needed | Free (local) | Run local LLMs via [ollama.com](https://ollama.com). Requires `ollama pull llama3.1` |
| None | `none` | — | — | AI features disabled; deterministic defaults used |

All provider configuration uses environment variables. The active provider is selected via `LLM_PROVIDER`. Model, base URL, and other parameters are configurable via `LLM_MODEL`, `LLM_BASE_URL`, `LLM_MAX_TOKENS`, and `LLM_TEMPERATURE`.

---

## Evidence, Provenance, and Confidence

Every observation stored in the system records:

- **Source adapter** — which collector produced the data (e.g., `dns`, `whois`, `ct`)
- **Collection timestamp** — when the data was collected
- **Raw response** — the unmodified API response (stored as JSONB)
- **Method** — the specific query or endpoint used
- **Target** — what was queried

Confidence scores are calculated using a multi-factor formula:

```
score = source_reliability × data_quality × corroboration_bonus × recency_factor
```

- **Source reliability** — weight by collector type (e.g., DNS A records scored higher than text search)
- **Data quality** — completeness of the response fields
- **Corroboration** — boost when the same entity appears across multiple independent sources
- **Recency** — decay over time based on observation timestamps

Entities and relationships carry `confidence` fields (0.0–1.0) that are displayed in the UI and included in reports.

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|---|---|---|
| Web framework | FastAPI | Async API, OpenAPI auto-docs |
| Database (relational) | PostgreSQL 16 + asyncpg | Investigations, observations, entities, reports |
| Database (graph) | Neo4j 5 Community | Knowledge graph (entities + relationships) |
| Cache / message broker | Redis 7 | Collector response caching, Celery broker |
| Task queue | Celery + Redis | Background OSINT collection (optional) |
| HTTP client | httpx | Async outbound requests for collectors |
| DNS | dnspython | DNS record queries |
| WHOIS | python-whois | Domain registration data |
| HTML parsing | BeautifulSoup4 | Web page metadata extraction |
| Reporting | Jinja2 + WeasyPrint | HTML/PDF report generation |
| Validation | Pydantic v2 | Request/response schemas, settings |
| Linting | Ruff | Python linting and formatting |

### Frontend

| Component | Technology | Purpose |
|---|---|---|
| Framework | React 19 + TypeScript | UI components |
| Build tool | Vite 8 | Dev server, bundling |
| Styling | Tailwind CSS 4 | Utility-first CSS |
| UI components | Custom CSS + Lucide + TailwindCSS | Accessible, composable components |
| State management | Zustand | Client-side state |
| Data fetching | TanStack Query | Server state, caching, background refetch |
| Forms | React Hook Form + Zod | Type-safe form validation |
| Graph visualization | Cytoscape.js | Interactive knowledge graph |
| Tables | TanStack Table | Sortable, filterable data tables |
| Charts | Recharts | Investigation metrics |
| Icons | Lucide React | Consistent icon set |

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   │   ├── investigations.py
│   │   │   ├── entities.py
│   │   │   ├── graph.py
│   │   │   ├── activity.py
│   │   │   └── reports.py
│   │   ├── core/             # Configuration, security, Redis client
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── redis.py
│   │   ├── services/         # Business logic pipeline
│   │   │   ├── classifier.py
│   │   │   ├── normalizer.py
│   │   │   ├── extractor.py
│   │   │   ├── resolver.py
│   │   │   ├── confidence.py
│   │   │   ├── relationship_detector.py
│   │   │   ├── correlator.py
│   │   │   ├── orchestrator.py
│   │   │   ├── investigation.py
│   │   │   ├── pivot_selector.py
│   │   │   ├── report_data.py
│   │   │   └── report_generator.py
│   │   ├── collectors/       # OSINT source adapters
│   │   │   ├── base.py
│   │   │   ├── cache.py
│   │   │   ├── rate_limiter.py
│   │   │   ├── retry.py
│   │   │   ├── registry.py
│   │   │   ├── dns_collector.py
│   │   │   ├── whois_collector.py
│   │   │   ├── ct_collector.py
│   │   │   ├── ip_asn_collector.py
│   │   │   ├── github_collector.py
│   │   │   ├── http_collector.py
│   │   │   └── threat_intel_collector.py
│   │   ├── ai/               # LLM integration
│   │   │   ├── planner.py
│   │   │   ├── analyzer.py
│   │   │   └── validator.py
│   │   ├── graph/            # Neo4j integration
│   │   │   ├── client.py
│   │   │   ├── reader.py
│   │   │   ├── writer.py
│   │   │   ├── queries.py
│   │   │   └── models.py
│   │   ├── db/               # PostgreSQL integration
│   │   │   ├── client.py
│   │   │   ├── models.py
│   │   │   └── migrations/
│   │   │       └── init.sql
│   │   ├── models/           # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── processing.py
│   │   │   └── ai.py
│   │   ├── tasks/            # Celery tasks
│   │   │   ├── celery_app.py
│   │   │   ├── collect.py
│   │   │   └── run_investigation.py
│   │   └── templates/
│   │       └── report.html
│   ├── tests/                # 285 backend tests
│   │   ├── test_classifier.py
│   │   ├── test_normalizer.py
│   │   ├── test_normalizer_phase4.py
│   │   ├── test_extractor.py
│   │   ├── test_confidence.py
│   │   ├── test_resolver.py
│   │   ├── test_relationship_detector.py
│   │   ├── test_collectors_infra.py
│   │   ├── test_dns_collector.py
│   │   ├── test_ct_collector.py
│   │   ├── test_whois_collector.py
│   │   ├── test_remaining_collectors.py
│   │   ├── test_report_generation.py
│   │   ├── test_integration_phase9.py
│   │   ├── test_performance.py
│   │   ├── test_api_contracts.py
│   │   ├── test_investigations_api.py
│   │   ├── test_activity_api.py
│   │   ├── test_phase5_integration.py
│   │   ├── test_phase6_integration.py
│   │   └── fixtures/
│   │       └── seed_data.py
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # React components
│   │   ├── hooks/            # TanStack Query hooks
│   │   ├── pages/            # Route pages
│   │   ├── store/            # Zustand state
│   │   ├── lib/              # Utilities
│   │   ├── __tests__/        # 13 frontend tests
│   │   ├── test/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.app.json
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── .env.example
├── PROJECT_SPECIFICATION.md
├── TECH_STACK.md
└── TASKS.md
```

---

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend build and dev server |
| npm | 9+ | Frontend package management |
| Docker | 24+ | Database containers |
| Docker Compose | v2 | Multi-container orchestration |

---

## Configuration

Copy `.env.example` to `.env` and adjust values. All settings have sensible defaults for local development.

### Required Settings

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_HOST` | PostgreSQL hostname | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_USER` | PostgreSQL username | `osintnexus` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `osintnexus_dev` |
| `POSTGRES_DB` | PostgreSQL database name | `osintnexus` |
| `NEO4J_URI` | Neo4j bolt URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `osintnexus_dev` |
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Redis database number | `0` |

### Optional: OSINT API Keys

Collectors with missing keys are automatically disabled. Investigations proceed with available sources.

| Variable | Service | Free Tier |
|---|---|---|
| `GITHUB_TOKEN` | GitHub API | 5,000 requests/hr |
| `ABUSEIPDB_API_KEY` | AbuseIPDB | 1,000 requests/day |
| `URLHAUS_API_KEY` | URLhaus | Free |

### Optional: AI/LLM Provider

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | Active provider: `nvidia`, `openai`, `anthropic`, `ollama`, or `none` | `none` |
| `LLM_API_KEY` | API key for the selected provider (not needed for Ollama) | (empty) |
| `LLM_MODEL` | Model name; if empty, uses provider default | (provider default) |
| `LLM_BASE_URL` | API base URL; if empty, uses provider default | (provider default) |
| `LLM_MAX_TOKENS` | Maximum tokens per LLM response | `2048` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.3` |

When `LLM_PROVIDER=none` (the default), the AI planner returns deterministic pivot defaults and the analyzer returns a stub summary. The core investigation pipeline is fully functional without any LLM.

### Optional: Application Settings

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application display name | `OSINT Nexus` |
| `DEBUG` | Enable debug mode (verbose logging, permissive CORS) | `false` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173,http://localhost:3000` |
| `DNS_TIMEOUT` | DNS collector timeout (seconds) | `10` |
| `WHOIS_TIMEOUT` | WHOIS collector timeout (seconds) | `15` |
| `HTTP_TIMEOUT` | HTTP collector timeout (seconds) | `30` |
| `CT_TIMEOUT` | Certificate Transparency timeout (seconds) | `30` |
| `GITHUB_TIMEOUT` | GitHub API timeout (seconds) | `15` |

---

## Setup and Running

### 1. Start Databases

```bash
docker compose up -d
```

This starts PostgreSQL 16, Neo4j 5 Community, and Redis 7 with persistent volumes. The schema is auto-initialized from `backend/app/db/migrations/init.sql`.

Verify services are healthy:

```bash
docker compose ps
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` if needed. The defaults work for local development with Docker. The `.env` file belongs in `backend/` because that is the working directory when the FastAPI server starts.

### 3. Start Backend

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Optional: Start Celery Worker

For background OSINT collection tasks:

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## Testing and Quality Checks

### Backend Tests (285 tests, no database required)

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

**Test categories:**

| Category | Files | Count | Requires DB? |
|---|---|---|---|
| Unit tests (classifier, normalizer, extractor, confidence, resolver, relationship detector) | `test_classifier.py`, `test_normalizer.py`, `test_normalizer_phase4.py`, `test_extractor.py`, `test_confidence.py`, `test_resolver.py`, `test_relationship_detector.py` | ~180 | No |
| Collector infrastructure | `test_collectors_infra.py`, `test_dns_collector.py`, `test_ct_collector.py`, `test_whois_collector.py`, `test_remaining_collectors.py` | ~40 | No |
| Report generation | `test_report_generation.py` | 17 | No |
| Integration tests | `test_integration_phase9.py` | 25 | No |
| Performance benchmarks | `test_performance.py` | 7 | No |
| API contract tests | `test_api_contracts.py` | ~35 | **Yes** (PostgreSQL) |
| API integration tests | `test_investigations_api.py`, `test_activity_api.py` | ~15 | **Yes** (PostgreSQL) |

Tests requiring PostgreSQL use live database connections and are excluded from the default CI run.

### Frontend Tests (13 tests)

```bash
cd frontend
npx vitest run
```

### Lint and Type Check

```bash
# Python (Ruff)
cd backend
python -m ruff check app/

# TypeScript
cd frontend
npx tsc --noEmit
```

### Frontend Build

```bash
cd frontend
npx vite build
```

---

## Usage Example

### Create an Investigation via API

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Phishing domain investigation",
    "target": "suspicious-example.com",
    "depth": "standard"
  }'
```

Response:

```json
{
  "id": "a1b2c3d4-...",
  "name": "Phishing domain investigation",
  "target": "suspicious-example.com",
  "target_type": "domain",
  "status": "created",
  "depth": "standard",
  "created_at": "2026-09-04T12:00:00Z",
  "updated_at": "2026-09-04T12:00:00Z"
}
```

### Start the Investigation Loop

```bash
curl -X POST http://localhost:8000/api/v1/investigations/{id}/start
```

The orchestrator dispatches relevant collectors (DNS, WHOIS, CT, etc.), runs the normalization/extraction/resolution pipeline, stores observations in PostgreSQL, builds the knowledge graph in Neo4j, and optionally queries the AI planner for pivot suggestions.

### View the Knowledge Graph

```bash
curl http://localhost:8000/api/v1/investigations/{id}/graph
```

### Generate a Report

```bash
curl -X POST http://localhost:8000/api/v1/investigations/{id}/reports \
  -H "Content-Type: application/json" \
  -d '{"format": "html"}'
```

---

## API Reference

Full interactive documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check (returns version and status) |
| **Investigations** | | |
| `POST` | `/api/v1/investigations` | Create a new investigation |
| `GET` | `/api/v1/investigations` | List all investigations |
| `GET` | `/api/v1/investigations/{id}` | Get investigation details |
| `POST` | `/api/v1/investigations/{id}/start` | Start the investigation collection loop (launches Celery task) |
| `POST` | `/api/v1/investigations/{id}/stop` | Stop a running investigation |
| `GET` | `/api/v1/investigations/{id}/status` | Get detailed status (budget, entity/relationship counts) |
| **Entities** | | |
| `GET` | `/api/v1/entities/{id}?investigation_id={id}` | Get entity details |
| `GET` | `/api/v1/entities/{id}/evidence?investigation_id={id}` | Get evidence observations for an entity |
| `GET` | `/api/v1/entities/{id}/relationships?investigation_id={id}` | Get entity relationships from the knowledge graph |
| **Graph** | | |
| `GET` | `/api/v1/investigations/{id}/graph` | Get the knowledge graph (nodes + edges) |
| `GET` | `/api/v1/investigations/{id}/graph/paths?source_id={id}&target_id={id}` | Find multi-hop paths between two entities |
| **Activity** | | |
| `GET` | `/api/v1/investigations/{id}/activity` | Get investigation activity log |
| `GET` | `/api/v1/investigations/{id}/observations` | Get raw observation records |
| **AI** | | |
| `GET` | `/api/v1/investigations/{id}/ai-analysis` | Get AI-generated analysis |
| **Reports** | | |
| `POST` | `/api/v1/investigations/{id}/reports` | Generate a report (`html`, `pdf`, `json`, or `csv`) |
| `GET` | `/api/v1/investigations/{id}/reports` | List all reports |
| `GET` | `/api/v1/investigations/{id}/reports/{rid}` | Get report metadata |
| `GET` | `/api/v1/investigations/{id}/reports/{rid}/download` | Download report file |

---

## Reports and Export

OSINT Nexus supports four report formats:

| Format | Content | Use Case |
|---|---|---|
| `html` | Styled HTML with evidence provenance, entity tables, and relationship lists | Sharing with stakeholders, printing |
| `pdf` | PDF rendering of the HTML report | Formal documentation, archival |
| `json` | Structured JSON with all investigation data | Programmatic consumption, integration |
| `csv` | Tab-separated entities and observations tables | Spreadsheet analysis, data import |

All reports include source attribution (which collector produced each observation), timestamps, and confidence scores. Reports are stored on disk in `backend/reports_output/` and metadata is recorded in the `reports` database table.

---

## Security

OSINT Nexus implements multiple security layers:

### Input Validation and Sanitization

- **Parameterized SQL queries** — all PostgreSQL queries use asyncpg parameterized statements (no SQL injection)
- **SSRF protection** — outbound HTTP requests are validated against a blocklist of private/internal IP ranges, localhost, and cloud metadata endpoints (`core/security.py`)
- **Input validation** — targets are validated and sanitized (control character stripping, length limits, scheme validation)
- **AI output validation** — LLM responses are parsed against Pydantic schemas; hallucinated entity IDs are filtered against the actual graph

### Application Security

- **Security headers** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Strict-Transport-Security` (production only)
- **CORS** — restricted to configured origins; production mode limits allowed methods and headers
- **Error sanitization** — API error responses strip internal file paths, IP addresses, and connection strings
- **Path traversal protection** — file downloads validate that paths resolve within the designated reports directory
- **HTML escaping** — Jinja2 autoescape prevents XSS in generated reports

### Data Handling

- All external data (OSINT responses, LLM output) is treated as untrusted
- Raw collector responses are stored immutably for audit trails
- `.env` files containing secrets are git-ignored
- API keys are loaded from environment variables, never from source code

---

## Deployment

### Environment Variables for Production

```bash
DEBUG=false
POSTGRES_PASSWORD=<strong-random-password>
NEO4J_PASSWORD=<strong-random-password>
CORS_ORIGINS=["https://your-domain.com"]
```

### Docker Compose (Development)

The included `docker-compose.yml` is configured for local development.

To start the full stack (PostgreSQL, Neo4j, Redis, Backend, Celery, and Frontend):

```bash
docker compose up --build -d
```

To also start the optional SearXNG search provider, use the `searxng` profile:

```bash
docker compose --profile searxng up --build -d
```

Once running, access the application at:
- **Frontend UI:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

For production deployments:

1. Use managed database services (AWS RDS, GCP Cloud SQL, etc.) instead of Docker containers
2. Enable TLS for all database connections
3. Set strong, unique passwords for PostgreSQL, Neo4j, and Redis
4. Restrict `CORS_ORIGINS` to your actual frontend domain
5. Place the backend behind a reverse proxy (nginx, Caddy) with TLS termination
6. Use environment-specific configuration (secrets manager, not `.env` files)

### CI/CD

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push to `main`/`develop` and pull requests to `main`:

- **Backend lint** — Ruff check + format verification
- **Backend tests** — pytest (excluding DB-dependent tests)
- **Frontend lint** — TypeScript check
- **Frontend tests** — Vitest
- **Frontend build** — Vite production build

---

## Known Limitations

| Limitation | Description |
|---|---|
| **Database dependency** | PostgreSQL must be running for API operations. Some tests require live database connections. |
| **Neo4j optional** | The graph database enhances visualization but the system degrades gracefully if unavailable. |
| **Celery optional** | Background task processing requires Celery + Redis. Without it, investigations run synchronously. |
| **API rate limits** | Free-tier OSINT APIs have strict rate limits. The system respects these via token bucket rate limiting. |
| **LLM costs** | AI planner and analyzer calls consume LLM API tokens. Budget-aware users should monitor usage. |
| **No authentication** | The current version does not implement user authentication. Not intended for multi-user production use. |
| **Single-user design** | Designed for individual investigators, not team collaboration. |

---

## Troubleshooting

### PostgreSQL Connection Refused

```bash
# Verify Docker container is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Restart if needed
docker compose restart postgres
```

### Neo4j Unavailable

The system starts without Neo4j. Graph features will be unavailable but the investigation pipeline continues. Check:

```bash
docker compose ps neo4j
docker compose logs neo4j
```

Default Neo4j credentials: `neo4j` / `osintnexus_dev` (change in `.env`).

### Frontend Build Errors

```bash
cd frontend
rm -rf node_modules
npm install
npx tsc --noEmit
```

### Backend Import Errors

Ensure you are running from the `backend/` directory and dependencies are installed:

```bash
cd backend
pip install -r requirements.txt
python -c "from app.main import app; print('OK')"
```

### Collector Timeouts

If specific collectors timeout, adjust the timeout values in `.env`:

```bash
DNS_TIMEOUT=15
WHOIS_TIMEOUT=20
HTTP_TIMEOUT=45
```

### Reports Directory

Generated reports are written to `backend/reports_output/`. Ensure the directory exists and is writable:

```bash
mkdir -p backend/reports_output
```

---

## Project Status

**Phase 9 complete.** All nine development phases have been implemented:

| Phase | Status | Description |
|---|---|---|
| 1. Scaffolding & Architecture | Complete | Project structure, databases, Docker, basic API |
| 2. Target Classification & Investigation Management | Complete | Classifier, normalizer, CRUD endpoints, frontend forms |
| 3. OSINT Collectors | Complete | DNS, WHOIS, CT, IP-to-ASN, GitHub, HTTP, threat intel |
| 4. Normalization, Extraction & Resolution | Complete | Entity extraction, deduplication, normalization pipeline |
| 5. Knowledge Graph | Complete | Neo4j integration, graph reader/writer, subgraph queries |
| 6. Investigation Orchestration | Complete | Automated collection loop, AI planner, pivot selection |
| 7. Dashboard & Visualization | Complete | React frontend, graph view, entity panels, timeline |
| 8. Reporting & Export | Complete | HTML/PDF/JSON/CSV report generation with provenance |
| 9. Testing, Security & Deployment | Complete | 285+ backend tests, 13 frontend tests, security hardening, CI |

**Test coverage:** 285 backend tests + 13 frontend tests passing. Ruff lint and TypeScript type checks clean.

---

## License

Academic use only. This project was developed as an academic endeavor. For commercial or production use, consult the project specification documents (`PROJECT_SPECIFICATION.md`, `TECH_STACK.md`).
