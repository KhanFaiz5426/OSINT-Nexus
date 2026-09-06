# TECH STACK

## OSINT Nexus: Technology Stack Specification

**Version:** 1.0  
**Date:** 2026-09-03  

---

## 1. Stack Selection Principles

| Principle | Weight | Notes |
|---|---|---|
| **Stability** | Critical | Must not break under normal use; battle-tested libraries preferred |
| **Current maintenance** | Critical | Actively maintained; security patches shipped promptly |
| **Security** | Critical | No known unpatched vulnerabilities; sane defaults |
| **Ecosystem** | High | Sufficient libraries, community support, documentation |
| **Developer experience** | High | Student team must be productive quickly |
| **Performance** | Medium | Adequate for investigation-scale workloads (not big data) |
| **Cost** | High | Open-source preferred; paid services only when essential |
| **AI integration** | Medium | Clean API for LLM calls; structured output support |
| **OSINT integration** | Medium | Python ecosystem dominates OSINT tooling |
| **Long-term viability** | Medium | Technology should exist in 3+ years |
| **Project complexity** | High | Minimal cognitive overhead; few moving parts |

**Decision rule:** Prefer one mature technology per layer. Newer technologies only when they provide a measurable, meaningful advantage over the mature alternative.

---

## 2. Frontend

### Selection: React + TypeScript + Vite

| Component | Choice | Reasoning |
|---|---|---|
| **Language** | TypeScript | Type safety; catches errors early; excellent IDE support |
| **Framework** | React 18+ | Largest ecosystem; most component libraries; student familiarity |
| **Build tool** | Vite | Fast HMR; simple config; modern defaults |
| **UI system** | Custom CSS + Lucide + TailwindCSS | Hand-crafted components with Lucide icons and Tailwind utility classes; no vendor lock-in |
| **Styling** | Tailwind CSS | Utility-first; rapid prototyping; consistent design tokens; no CSS-in-JS runtime overhead |
| **State management** | Zustand | Minimal API; no boilerplate; sufficient for investigation state |
| **Data fetching** | TanStack Query (React Query) | Server state management; caching; background refetching; optimistic updates |
| **Form handling** | React Hook Form + Zod | Lightweight; type-safe validation; minimal re-renders |
| **Graph visualization** | Cytoscape.js | Industry standard for interactive graph visualization; large node support; layout algorithms built-in |
| **Tables** | TanStack Table | Headless; virtual scrolling support; sorting, filtering, pagination |
| **Icons** | Lucide React | Consistent icon set; tree-shakeable; minimal bundle |
| **Charts** | Recharts | Simple API; composable; sufficient for investigation metrics |

### Frontend Requirements

The dashboard must support:
- Interactive knowledge graph (100+ nodes, zoomable, filterable)
- Evidence panels with expandable raw data
- Investigation timeline (chronological events)
- Entity list with search and filtering
- AI analysis display (text-based findings)
- Real-time updates during investigation
- Report preview and export

---

## 3. UI / UX Design

### Design Direction: Professional Investigation Workstation

The interface should feel like a **data analyst's workstation**, not a consumer app or a cyberpunk terminal.

| Characteristic | Implementation |
|---|---|
| **Minimal** | No decorative elements; every pixel serves a purpose |
| **Information-dense** | Use space efficiently; compact layouts; avoid wasted whitespace |
| **Strong visual hierarchy** | Clear distinction between primary, secondary, and tertiary information |
| **Excellent typography** | Inter or system font stack; consistent sizing scale; adequate line height |
| **Restrained color palette** | Neutral base (grays, whites); single accent color for actions; semantic colors for status only |
| **Fast** | No unnecessary animations; instant feedback on interactions |

### Recommended Design System

| Choice | Why |
|---|---|
| **Custom CSS** | Tailwind CSS 4 with CSS variables for theming; no runtime overhead |
| **Tailwind CSS** | Utility-first prevents style drift; design tokens via tailwind.config; fast iteration |
| **Inter font** | Optimized for screens; neutral; excellent readability at small sizes; free |

### Visual Identity

| Element | Approach |
|---|---|
| Background | White or very light gray (`#fafafa`) |
| Cards/panels | Subtle borders (`border-gray-200`); no shadows or minimal shadows |
| Text | `gray-900` primary; `gray-500` secondary; `gray-300` disabled |
| Accent | Single blue (e.g., `blue-600`) for primary actions |
| Success | `green-600` — used sparingly for status indicators |
| Warning | `amber-500` — for warnings and medium-confidence items |
| Error | `red-600` — for errors and high-risk indicators |
| Graph nodes | Color-coded by entity type (5–7 colors max) |
| Borders | `1px solid` — thin, clean lines |

### Avoid

- Neon/cyberpunk color schemes
- Gradient backgrounds on cards
- Glowing borders or shadows
- Large border-radius on data-heavy components
- Animated backgrounds or floating elements
- "Glassmorphism" over content areas
- Excessive icon usage where text is clearer
- Dark mode as default (light mode is better for readability in professional settings; dark mode can be a future option)

---

## 4. Backend

### Selection: Python + FastAPI

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Python + FastAPI** | Async; type hints; automatic OpenAPI docs; strong OSINT ecosystem; Pydantic validation; async for concurrent OSINT calls | GIL limits CPU-bound parallelism (not a problem for I/O-bound OSINT) | **Selected** |
| Node.js + NestJS | JavaScript full-stack; good async | Weaker OSINT ecosystem; less mature for data processing | Rejected |
| Go | Excellent performance; strong concurrency | Steeper learning curve; weaker OSINT/NLP ecosystem; overkill for this project | Rejected |
| Python + Django | Mature; admin UI; ORM | Synchronous by default; heavier; less modern API design | Rejected |

### Why Python + FastAPI

1. **OSINT ecosystem.** Nearly all OSINT tools and libraries are Python (dnspython, python-whois, shodan, etc.). Choosing anything else means reimplementing or wrapping Python libraries.
2. **Async I/O.** FastAPI is async-native. OSINT collection is I/O-bound (many concurrent API calls). This fits perfectly.
3. **Type safety.** Pydantic models enforce data shapes at API boundaries. Catches errors before they propagate.
4. **Auto-generated docs.** FastAPI generates OpenAPI spec automatically. No separate documentation step.
5. **Student familiarity.** Python is commonly taught; lower barrier for student teams.

### Backend Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app initialization
│   ├── api/                  # Route handlers
│   │   ├── investigations.py
│   │   ├── entities.py
│   │   ├── graph.py
│   │   └── reports.py
│   ├── core/                 # Config, security, dependencies
│   │   ├── config.py
│   │   ├── security.py
│   │   └── deps.py
│   ├── models/               # Pydantic schemas
│   │   ├── investigation.py
│   │   ├── entity.py
│   │   ├── observation.py
│   │   └── report.py
│   ├── services/             # Business logic
│   │   ├── orchestrator.py
│   │   ├── classifier.py
│   │   ├── normalizer.py
│   │   ├── extractor.py
│   │   ├── resolver.py
│   │   ├── correlator.py
│   │   ├── confidence.py
│   │   └── planner.py
│   ├── collectors/           # OSINT source adapters
│   │   ├── base.py           # Adapter interface
│   │   ├── dns_collector.py
│   │   ├── whois_collector.py
│   │   ├── ct_collector.py
│   │   ├── github_collector.py
│   │   ├── http_collector.py
│   │   ├── threat_intel_collector.py
│   │   └── search_collector.py
│   ├── ai/                   # LLM integration
│   │   ├── planner.py
│   │   ├── analyzer.py
│   │   └── reporter.py
│   ├── graph/                # Neo4j integration
│   │   ├── client.py
│   │   ├── queries.py
│   │   └── models.py
│   └── db/                   # PostgreSQL integration
│       ├── client.py
│       ├── models.py
│       └── migrations/
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

## 5. OSINT Collector Architecture

### Collector Interface

Every OSINT collector implements a common interface:

```python
class OSINTCollector(Protocol):
    name: str
    version: str
    supported_target_types: list[TargetType]
    requires_api_key: bool

    async def collect(
        self, target: str, target_type: TargetType
    ) -> RawResult: ...

    def health_check(self) -> bool: ...
```

### Adapter Pattern

| Concern | Implementation |
|---|---|
| **Interface** | All collectors implement `OSINTCollector` protocol; same input/output shape |
| **Error handling** | Collectors return `RawResult` with `status: success | error | timeout`; never raise unhandled exceptions |
| **Retries** | Retry with exponential backoff (3 attempts, 1s/2s/4s delays) for transient failures (429, 503, timeout) |
| **Rate limiting** | Per-collector rate limiter using token bucket algorithm; configurable requests/minute |
| **Caching** | Redis cache keyed by `{collector}:{target}:{target_type}`; TTL per collector (default 24h) |
| **API keys** | Loaded from environment variables; collector checks key availability on initialization |
| **Source failures** | Failed collectors logged; investigation continues with remaining sources; partial results used |

### Rate Limit Configuration

| Collector | Default Rate Limit | Notes |
|---|---|---|
| DNS | 10 req/s | Public resolvers have generous limits |
| WHOIS/RDAP | 5 req/s | Some registries rate-limit aggressively |
| Certificate Transparency | 1 req/s | crt.sh has limited capacity |
| GitHub API | 30 req/min (unauthenticated) | 5000 req/min with token |
| HTTP analysis | 5 req/s | Self-imposed polite limit |
| Threat intelligence | 4 req/min (AbuseIPDB free tier) | Strict per-source limits |
| Search engines | 1 req/s | Varies by provider |

---

## 6. Database / Storage

### Selection: PostgreSQL + Neo4j + Redis

| Database | Role | Why |
|---|---|---|
| **PostgreSQL** | Primary document store | Investigations, observations, evidence records, user data; JSONB for flexible schemas; full-text search built-in |
| **Neo4j** | Knowledge graph | Native graph storage; Cypher query language; efficient relationship traversal; purpose-built for connected data |
| **Redis** | Cache + task queue | API response caching; session storage; Celery broker; pub/sub for real-time updates |

### Why Not Alternatives

| Rejected | Why |
|---|---|
| SQLite | Insufficient for concurrent access; no graph capabilities; no full-text search |
| MongoDB | Less mature than PostgreSQL for structured data; weaker ACID guarantees; no native graph |
| Elasticsearch | Overkill for this project's scale; adds significant operational complexity; PostgreSQL full-text search is sufficient |
| MySQL | Less feature-rich than PostgreSQL; no native JSONB; weaker ecosystem for this use case |
| Dgraph / ArangoDB | Less mature; smaller community; Neo4j is the standard for knowledge graphs |

### PostgreSQL Schema (Simplified)

```sql
-- Investigations
CREATE TABLE investigations (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    target_type TEXT NOT NULL,
    status TEXT DEFAULT 'created',
    depth TEXT DEFAULT 'standard',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Observations (immutable evidence)
CREATE TABLE observations (
    id UUID PRIMARY KEY,
    investigation_id UUID REFERENCES investigations(id),
    source_adapter TEXT NOT NULL,
    source_version TEXT,
    collected_at TIMESTAMPTZ NOT NULL,
    method TEXT NOT NULL,
    target TEXT NOT NULL,
    raw_response JSONB NOT NULL,
    normalized_value TEXT,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entities
CREATE TABLE entities (
    id TEXT PRIMARY KEY,  -- e.g., "domain:example.com"
    investigation_id UUID REFERENCES investigations(id),
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence FLOAT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Investigation activity log
CREATE TABLE activity_log (
    id BIGSERIAL PRIMARY KEY,
    investigation_id UUID REFERENCES investigations(id),
    event_type TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. Knowledge Graph

### Selection: Neo4j

**Storage:** Neo4j Community Edition (free, sufficient for this project)

**Nodes:** Each entity type becomes a node label; properties include value, confidence, timestamps.

**Relationships:** Each relationship type becomes a Neo4j relationship type; properties include confidence, evidence list, discovery method.

**Cypher Example:**

```cypher
// Create domain node
MERGE (d:Domain {value: 'example.com'})
SET d.confidence = 0.95, d.first_seen = datetime()

// Create IP node
MERGE (ip:IP {value: '1.2.3.4'})
SET ip.confidence = 0.95

// Create relationship
MERGE (d)-[r:HOSTED_ON]->(ip)
SET r.confidence = 0.95, r.evidence = ['obs_001', 'obs_002']

// Query: find all domains on same IP
MATCH (d:Domain)-[:HOSTED_ON]->(ip:IP {value: '1.2.3.4'})
RETURN d.value, d.confidence
```

**Integration:** FastAPI backend uses `neo4j` Python driver. Graph queries are executed through a dedicated `graph/` module. Frontend fetches graph data via REST API and renders with Cytoscape.js.

---

## 8. AI / LLM

### Selection: Direct API calls (OpenAI or Anthropic)

| Approach | Verdict |
|---|---|
| **Direct API (OpenAI / Anthropic)** | **Selected** — Simple; reliable; structured output support; no framework overhead |
| LangChain | Rejected — Adds unnecessary abstraction; opaque; debugging difficulty; most functionality can be implemented in 50 lines |
| LangGraph | Rejected — Useful for complex agent workflows; overkill for this project's linear investigation loop |
| LlamaIndex | Rejected — Designed for RAG/retrieval; not relevant to investigation planning |
| Local models (Ollama) | Rejected for MVP — Insufficient quality for investigation reasoning; adds GPU/VRAM requirements; useful for future self-hosted option |
| Hugging Face pipelines | Rejected — Better for classification/embedding; not for multi-step reasoning |

### Why Direct API

1. **Minimal code.** LLM calls are HTTP requests with JSON. No framework needed.
2. **Structured output.** OpenAI and Anthropic support JSON mode and tool use. Direct API gives full control.
3. **Debugging.** When something fails, you see the exact request/response. No framework abstractions hiding errors.
4. **Cost control.** Direct API means you control token usage explicitly.
5. **Portability.** Switching providers requires changing one API client, not rewriting framework code.

### AI Use Cases

| Task | Implementation |
|---|---|
| **Investigation planning** | Prompt LLM with current graph state; ask for recommended pivots with reasoning; parse JSON response |
| **Pivot selection** | Same as planning; focus on ranking and cost estimation |
| **Unstructured text interpretation** | Feed web page content, search snippets to LLM; extract entities and relationships |
| **Entity matching** | Feed two entity descriptions; ask if they refer to the same real-world entity |
| **Relationship explanation** | Feed graph context; ask LLM to explain significance of a relationship in natural language |
| **Finding prioritization** | Feed all findings; ask LLM to rank by relevance to investigation goals |
| **Summarization** | Feed collected data; ask LLM to produce concise overview |
| **Report generation** | Feed structured findings; ask LLM to produce prose report sections |

### AI Safety Rules

| Rule | Implementation |
|---|---|
| **AI is never the source of evidence** | LLM outputs are labeled as "AI Assessment" or "AI Recommendation"; never stored as observations |
| **Deterministic data first** | LLM receives only data that has been collected, normalized, and validated by deterministic code |
| **Structured output** | LLM responses are parsed as JSON; invalid responses are retried or discarded |
| **Temperature = 0** for factual tasks | Minimizes hallucination for entity matching and factual questions |
| **Temperature = 0.7** for planning/creative tasks | Allows some reasoning variation for investigation planning |
| **Source verification** | LLM cannot invent sources; all sources in AI output must reference existing observations |

---

## 9. AI Orchestration

### Investigation Loop

```
Target → Classifier → Planner → Collect → Normalize → Extract →
Resolve → Correlate → AI Analyze → Pivot? → Collect → ... → Report
```

### Implementation: Deterministic orchestrator with AI advisory

The orchestrator is **deterministic Python code** that manages the investigation lifecycle. AI is called at specific decision points, not controlling the loop.

```python
async def investigation_loop(investigation_id: str, max_depth: int = 4):
    depth = 0
    while depth < max_depth:
        # 1. Observe (deterministic)
        observations = await collect(investigation_id)

        # 2. Process (deterministic)
        entities = normalize_and_extract(observations)
        resolve_entities(entities)
        update_graph(entities)

        # 3. AI advisory (AI call)
        state = get_graph_state(investigation_id)
        recommendations = await ai_plan_pivots(state)

        # 4. Decide (deterministic, based on AI input)
        next_actions = select_permitted_actions(
            recommendations,
            budget=get_remaining_budget(investigation_id),
            rate_limits=get_rate_limits()
        )

        if not next_actions:
            break  # No viable pivots

        # 5. Execute next actions
        dispatch_collection_tasks(next_actions)
        depth += 1

    # Generate report
    generate_report(investigation_id)
```

### Preventing Problems

| Problem | Prevention |
|---|---|
| **Infinite loops** | Hard depth limit (configurable, default 4); no loop without new observations |
| **Excessive API calls** | Per-investigation budget counter; checked before every collection dispatch |
| **Hallucinated evidence** | AI outputs stored separately from observations; never referenced as source data |
| **Fabricated sources** | AI output parser validates that referenced observation IDs exist in the database |
| **Uncontrolled tool usage** | Orchestrator dispatches collectors; AI never directly calls APIs |
| **Rate limit violations** | Per-collector rate limiter; queue respects limits; backpressure on overflow |

---

## 10. Search / Indexing

### Selection: PostgreSQL full-text search

**Why not a dedicated search engine:**

| Alternative | Why Rejected |
|---|---|
| Elasticsearch | Adds significant operational complexity; separate cluster to maintain; overkill for project scale |
| Meilisearch | Good option but adds another service; PostgreSQL FTS is sufficient |
| Typesense | Same as Meilisearch; adds complexity without proportional benefit |

**PostgreSQL FTS is sufficient for:**
- Searching entities by value (domain name, IP, email)
- Searching observations by source adapter, target, or content
- Searching investigation names and descriptions
- Filtering entities by type, confidence range, date range

**When to reconsider:** If search performance degrades beyond acceptable limits (>500ms for complex queries on large datasets), migrate to Meilisearch or Elasticsearch.

---

## 11. Background Jobs / Queues

### Selection: Celery + Redis

| Option | Verdict |
|---|---|
| **Celery + Redis** | **Selected** — Mature; well-documented; sufficient for this workload; Redis doubles as cache |
| Redis Queue (rq) | Rejected — Simpler but less feature-rich; no built-in rate limiting; fewer monitoring options |
| Dramatiq | Rejected — Good alternative but smaller community; Celery is more established |
| RabbitMQ | Rejected — Adds separate message broker; Redis is sufficient as broker for this scale |
| Kafka | Rejected — Massive overkill; designed for high-throughput streaming, not investigation tasks |

### Celery Configuration

```python
# Task routing
CELERY_TASK_ROUTES = {
    'app.tasks.collect_dns': {'queue': 'osint'},
    'app.tasks.collect_whois': {'queue': 'osint'},
    'app.tasks.collect_ct': {'queue': 'osint'},
    'app.tasks.ai_analyze': {'queue': 'ai'},
    'app.tasks.generate_report': {'queue': 'reports'},
}

# Concurrency
CELERY_WORKER_CONCURRENCY = 4  # Limit concurrent OSINT tasks
CELERY_TASK_TIME_LIMIT = 60     # Kill tasks after 60s
CELERY_TASK_SOFT_TIME_LIMIT = 45  # Warning at 45s
```

---

## 12. Reporting

| Format | Technology | Use Case |
|---|---|---|
| **HTML** | Jinja2 templates | Interactive reports; preview in browser |
| **PDF** | WeasyPrint | Printable reports; formal documentation |
| **JSON** | Python dict → JSON dump | Machine-readable; integration with other tools |
| **CSV** | Python csv module | Entity/observation export for spreadsheets |

### Why These Choices

- **Jinja2** is the standard Python templating engine; familiar to most Python developers
- **WeasyPrint** converts HTML to PDF; uses standard CSS for print styling; no external service needed
- **JSON** is native Python; no library needed
- **CSV** is stdlib; no dependency

---

## 13. Security

| Concern | Approach |
|---|---|
| **Authentication** | Session-based auth (fastapi-users or custom JWT); bcrypt password hashing |
| **Authorization** | Role-based (admin/analyst/viewer); enforced at API route level |
| **API security** | HTTPS enforced; CORS configured; rate limiting on auth endpoints |
| **Secrets** | Environment variables; never in code; `.env` file excluded from git |
| **API keys** | Stored in environment variables or secrets manager; not in database |
| **Rate limiting** | Per-IP and per-user rate limits using `slowapi` or Redis-based limiter |
| **Audit logs** | All investigation actions logged in `activity_log` table; immutable |
| **Input validation** | Pydantic models on all API inputs; regex validation for targets; SQL injection prevented by parameterized queries |

---

## 14. Development Tooling

| Tool | Purpose |
|---|---|
| **Docker** | Containerize backend, frontend, databases for reproducible development |
| **Docker Compose** | Orchestrate all services locally with one command |
| **Git** | Version control; branch-based workflow |
| **GitHub Actions** | CI/CD: lint, test, build on push |
| **Ruff** | Python linting (replaces flake8, isort, pyupgrade); extremely fast |
| **Black** | Python code formatting; opinionated; zero config |
| **mypy** | Python static type checking; integrates with Pydantic |
| **ESLint + Prettier** | TypeScript/React linting and formatting |
| **pytest** | Python testing framework; fixtures; parametrize; markers |
| **Vitest** | Frontend testing; Vite-native; fast |
| **Playwright** | End-to-end browser testing |
| **Swagger UI / ReDoc** | Auto-generated API documentation from FastAPI OpenAPI spec |

---

## 15. Testing Stack

| Test Type | Tool | What It Tests |
|---|---|---|
| **Unit tests** | pytest | Individual functions: normalization, extraction, confidence scoring |
| **Integration tests** | pytest + httpx | API endpoints; database interactions; collector integration |
| **Collector tests** | pytest + recorded responses (VCR/ responses) | Each collector against recorded API responses; no live API calls in CI |
| **Correlation tests** | pytest | Entity resolution; relationship detection; graph updates |
| **API tests** | httpx + pytest | REST API contract testing |
| **Frontend tests** | Vitest + React Testing Library | Component rendering; user interactions |
| **E2E tests** | Playwright | Full investigation workflow in browser |
| **AI validation** | pytest + golden dataset | Compare AI outputs against expected responses for planning/summarization tasks |

---

## 16. Final Recommended Stack

```
Frontend:
  Language:       TypeScript
  Framework:      React 18+ (Vite)
  UI:             Custom CSS + Lucide + TailwindCSS
  Styling:        Tailwind CSS
  Graph:          Cytoscape.js
  Charts:         Recharts
  State:          Zustand
  Data fetching:  TanStack Query
  Forms:          React Hook Form + Zod
  Tables:         TanStack Table
  Icons:          Lucide React
  Font:           Inter

Backend:
  Language:       Python 3.12+
  Framework:      FastAPI
  API style:      REST (OpenAPI auto-generated)
  Validation:     Pydantic v2

OSINT:
  Architecture:   Adapter pattern (OSINTCollector protocol)
  Collectors:     DNS, WHOIS, CT, GitHub, HTTP, Threat Intel, Search
  Rate limiting:  Token bucket per collector
  Caching:        Redis (TTL per collector)

Database:
  Primary:        PostgreSQL 16+
  Graph:          Neo4j 5+ Community Edition
  Cache:          Redis 7+

AI / LLM:
  Provider:       OpenAI API (GPT-4o) or Anthropic API (Claude)
  Integration:    Direct HTTP calls (no framework)
  Structured:     JSON mode / tool use
  Safety:         AI outputs separate from evidence; temperature control

Background jobs:
  Queue:          Celery 5+
  Broker:         Redis

Search:
  Engine:         PostgreSQL full-text search

Reports:
  HTML:           Jinja2
  PDF:            WeasyPrint
  JSON:           Native Python
  CSV:            Python csv module

DevOps:
  Containers:     Docker + Docker Compose
  CI/CD:          GitHub Actions
  Linting:        Ruff (Python), ESLint (TypeScript)
  Formatting:     Black (Python), Prettier (TypeScript)
  Type checking:  mypy (Python), TypeScript compiler

Testing:
  Backend:        pytest
  Frontend:       Vitest
  E2E:            Playwright
  Collector:      pytest + recorded responses
```

---

## 17. Alternatives

| Technology | Why Not Chosen | When It Would Make Sense |
|---|---|---|
| **Next.js** | Server-side rendering unnecessary for this SPA; Vite is simpler | If SEO or server-rendered pages were needed |
| **Vue / Svelte** | Smaller ecosystem than React; fewer component libraries | If team had strong Vue/Svelte preference |
| **Django** | Heavier; synchronous by default; less modern API design | If admin UI and ORM were primary needs |
| **Go** | Weaker OSINT/NLP ecosystem; steeper learning curve | If raw performance was the primary bottleneck |
| **MongoDB** | Less mature for structured data; weaker ACID | If schema flexibility was more important than consistency |
| **Elasticsearch** | Operational complexity; overkill for project scale | If search performance on large datasets became critical |
| **RabbitMQ** | Separate broker; Redis is sufficient | If message throughput exceeded Redis capabilities |
| **LangChain** | Opaque abstraction; debugging difficulty; unnecessary for this scope | If building complex multi-agent systems |
| **Ollama** | Insufficient model quality for reasoning tasks | If self-hosted/inference cost was critical for production |
| **Meilisearch** | Adds another service; PostgreSQL FTS sufficient | If search latency on large datasets degraded |

---

## 18. Technology Decision Table

| Category | Recommended | Alternatives | Why Recommended |
|---|---|---|---|
| Frontend framework | React 18+ | Vue, Svelte | Largest ecosystem; most libraries; team familiarity |
| Build tool | Vite | Webpack, CRA | Fast; modern; simple config |
| UI components | Custom CSS + Lucide + TailwindCSS | Material UI, Ant Design, Chakra | Hand-crafted; accessible; no vendor lock-in |
| Styling | Tailwind CSS | CSS Modules, Styled Components | Utility-first; fast; consistent tokens |
| Graph viz | Cytoscape.js | D3.js, vis.js, Sigma.js | Best balance of features and simplicity for graph rendering |
| Backend | FastAPI | Django REST, Flask, NestJS | Async-native; auto OpenAPI; Pydantic validation |
| Primary DB | PostgreSQL | MySQL, MongoDB, SQLite | Most features; JSONB; FTS; mature; reliable |
| Graph DB | Neo4j | ArangoDB, Dgraph, NetworkX | Industry standard for knowledge graphs; Cypher is expressive |
| Cache/Broker | Redis | Memcached, RabbitMQ | Doubles as cache and Celery broker; fast; reliable |
| Task queue | Celery | RQ, Dramatiq, Huey | Most mature; good monitoring; Redis broker |
| AI/LLM | OpenAI/Anthropic API | LangChain, LlamaIndex, local models | Direct control; no framework overhead |
| PDF generation | WeasyPrint | ReportLab, PDFKit | HTML→PDF via CSS; clean; maintainable |
| Python linting | Ruff | flake8, pylint | Replaces multiple tools; extremely fast |
| Python formatting | Black | autopep8, yapf | Opinionated; zero config; standard |
| Testing | pytest | unittest | Fixtures; parametrize; plugins; standard |
| E2E testing | Playwright | Cypress | Multi-browser; faster; better API |

---

## 19. Version / Stability Check

| Technology | Recommended Release | Maturity | Maintenance | Notes |
|---|---|---|---|---|
| **Python** | 3.12+ | Stable | Active (3.13 in development) | Verify exact latest stable before deployment |
| **FastAPI** | 0.115+ | Stable | Active (weekly releases) | Version needs verification at build time |
| **React** | 18.x | Stable | Active | React 19 available; 18.x is safer for ecosystem compatibility |
| **Vite** | 6.x | Stable | Active | Verify current stable release |
| **TypeScript** | 5.x | Stable | Active | Verify current stable |
| **Tailwind CSS** | 4.x | Stable | Active | v4 uses new engine; v3.x also viable if compatibility issues arise |
| **Custom CSS** | Latest | Stable | Active | Tailwind utility classes with CSS variables for theming |
| **Cytoscape.js** | 3.x | Stable | Active | Well-established; no major breaking changes expected |
| **Neo4j** | 5.x Community | Stable | Active | Community edition is free and sufficient |
| **PostgreSQL** | 16+ | Stable | Active | Verify current stable |
| **Redis** | 7.x | Stable | Active | Verify current stable |
| **Celery** | 5.x | Stable | Active | Verify current stable |
| **Pydantic** | 2.x | Stable | Active | v2 is current; v1 is legacy |
| **Zod** | 3.x | Stable | Active | Standard for TypeScript validation |
| **TanStack Query** | 5.x | Stable | Active | Verify current stable |
| **Cytoscape.js** | 3.x | Stable | Active | Well-established |
| **WeasyPrint** | 60+ | Stable | Active | Verify current stable |
| **pytest** | 8.x | Stable | Active | Verify current stable |
| **Playwright** | 1.x | Stable | Active | Verify current stable |

**Note:** Exact version numbers should be verified at project build time. Pin versions in `requirements.txt` (Python) and `package.json` (Node) for reproducibility.

---

## 20. Final Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  React + TypeScript + Tailwind CSS + Cytoscape.js           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Backend (Python 3.12+)                              │
│  ├── REST API (auto-generated OpenAPI docs)                  │
│  ├── Pydantic v2 validation                                 │
│  └── Authentication / Authorization                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌──────────────┐ ┌─────────────────┐ ┌──────────────┐
│ Investigation│ │   OSINT         │ │   AI Layer   │
│ Orchestrator │ │   Collectors    │ │   (LLM API)  │
│ (Celery)     │ │                 │ │              │
│              │ │ ├── DNS         │ │ ├── Planning  │
│ Manages loop │ │ ├── WHOIS       │ │ ├── Pivots    │
│ depth, budget│ │ ├── CT          │ │ ├── Analysis  │
│ rate limits  │ │ ├── GitHub      │ │ ├── Summary   │
│              │ │ ├── HTTP        │ │ └── Reports   │
│              │ │ ├── Threat Intel │ │              │
│              │ │ └── Search      │ │ Direct API   │
│              │ │                 │ │ (no framework)│
│              │ │ Adapter pattern │ │              │
│              │ │ Rate-limited    │ │              │
│              │ │ Cached          │ │              │
└──────┬───────┘ └────────┬────────┘ └──────┬───────┘
       │                  │                 │
       ▼                  ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Storage Layer                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Neo4j        │  │ Redis        │     │
│  │              │  │              │  │              │     │
│  │ Investigations│  │ Entities    │  │ API cache    │     │
│  │ Observations │  │ Relationships│  │ Session      │     │
│  │ Evidence     │  │ Knowledge   │  │ Celery broker│     │
│  │ Activity log │  │ Graph       │  │ Rate limits  │     │
│  │ Full-text    │  │ Cypher      │  │              │     │
│  │ search       │  │ queries     │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Reporting Engine                                            │
│  ├── Jinja2 → HTML reports                                  │
│  ├── WeasyPrint → PDF reports                               │
│  ├── JSON export                                            │
│  └── CSV export                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 21. UI Screen Structure

### Dashboard

| Aspect | Details |
|---|---|
| **Purpose** | Overview of all investigations; quick access to recent work |
| **Components** | Recent investigations list, create new investigation button, system status indicators |
| **Interactions** | Click investigation → open detail; create → new investigation form |

### Investigations

| Aspect | Details |
|---|---|
| **Purpose** | List and filter all investigations |
| **Components** | Filterable/sortable table (TanStack Table); status badges; target type indicators |
| **Interactions** | Search by name/target; filter by status/type; click → open detail |

### Investigation Detail

| Aspect | Details |
|---|---|
| **Purpose** | Main workspace for an active investigation |
| **Components** | Overview panel, entity list, graph view, timeline, AI analysis, activity log |
| **Interactions** | Select entity → show details; trigger pivot; stop investigation; export report |

### Entity Detail

| Aspect | Details |
|---|---|
| **Purpose** | Full view of a single entity and its relationships |
| **Components** | Entity properties, evidence table, connected entities, confidence breakdown |
| **Interactions** | Click connected entity → navigate; view raw evidence; view source |

### Knowledge Graph

| Aspect | Details |
|---|---|
| **Purpose** | Full-screen interactive graph visualization |
| **Components** | Cytoscape.js canvas; node/edge filters; zoom controls; layout controls |
| **Interactions** | Click node → entity detail; click edge → relationship detail; filter by type; search |

### Evidence

| Aspect | Details |
|---|---|
| **Purpose** | Browse all observations for an investigation |
| **Components** | Filterable table: source, timestamp, target, confidence; expandable raw data |
| **Interactions** | Filter by source/type/date; expand row → raw response; click entity → navigate |

### Reports

| Aspect | Details |
|---|---|
| **Purpose** | Generate and view investigation reports |
| **Components** | Report preview (HTML); export buttons (PDF, JSON, CSV); report history |
| **Interactions** | Generate report; preview; download; view previous reports |

### Settings

| Aspect | Details |
|---|---|
| **Purpose** | System configuration |
| **Components** | API key management; default investigation depth; notification preferences |
| **Interactions** | Add/remove API keys; set defaults |

---

## 22. Final Recommendation

### Why This Stack Fits OSINT Nexus

**Python + FastAPI** is the natural backend for an OSINT project. The entire OSINT tooling ecosystem is Python. Choosing anything else means fighting the ecosystem instead of leveraging it.

**React + TypeScript + Tailwind** produces a professional, maintainable frontend without framework lock-in. Custom CSS with Lucide icons gives accessible components without vendor dependency.

**PostgreSQL + Neo4j + Redis** covers all storage needs with minimal operational overhead. PostgreSQL handles documents, Neo4j handles graphs, Redis handles caching and queuing. Each does what it's best at.

**Direct LLM API calls** keep the AI layer simple and debuggable. No opaque framework between you and the model. When something goes wrong, you see the exact request and response.

### Why It Is Stable

Every recommended technology is mature, widely used, and actively maintained. React, Python, FastAPI, PostgreSQL, Neo4j, Redis, and Celery have been in production use for years. None are experimental or unproven.

### Why It Is Maintainable

The stack has few moving parts. Each technology has excellent documentation and large communities. A student team can learn the stack quickly and onboard new members without specialized knowledge.

### Why It Is Not Over-Engineered

There is no message broker beyond Redis. No service mesh. No Kubernetes. No GraphQL gateway. No microservices. The architecture is a monolithic backend with a separate frontend, three storage systems, and a task queue. This is the simplest architecture that supports the requirements.

### Why It Supports the Investigation Workflow

The orchestrator (Celery + Python) manages the investigation loop. Collectors are modular adapters. The correlation engine builds the knowledge graph. The AI layer provides advisory input. The frontend visualizes everything. Each component does one thing well, and they compose cleanly.

### Why It Can Produce a Professional UI

Custom CSS with Lucide icons provides accessible, customizable components that can be themed to any design language. Tailwind CSS enables rapid, consistent styling. Cytoscape.js provides industry-standard graph visualization. The result is a clean, information-dense interface suitable for professional analysts.

---

*End of tech stack specification.*
