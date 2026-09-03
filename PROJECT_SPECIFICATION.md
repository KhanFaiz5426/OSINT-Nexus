# PROJECT SPECIFICATION

## OSINT Nexus: An AI-Assisted OSINT Investigation and Correlation Framework

**Version:** 1.0  
**Date:** 2026-09-03  
**Document Type:** Functional & Technical Specification  

---

## 1. Project Overview

### 1.1 What OSINT Nexus Is

OSINT Nexus is a modular, end-to-end OSINT investigation framework that accepts an investigation target (domain, IP, URL, username, email, or organization), automatically collects publicly available information from open sources, normalizes heterogeneous data into a unified entity model, identifies relationships between entities, uses AI-assisted planning to suggest investigation pivots, and presents correlated intelligence with source attribution, confidence scoring, an interactive knowledge graph, and evidence-backed reporting.

### 1.2 The Problem

OSINT investigations today suffer from three structural problems:

1. **Fragmented workflow.** Analysts chain together standalone tools (DNS lookups, WHOIS queries, search engine dorks, certificate transparency searches, threat intel feeds). Each tool outputs data in a different format, requiring manual mental correlation across disparate sources.

2. **Manual pivot selection.** After initial collection, deciding which lead to follow next is expert judgment. Junior analysts miss high-value pivots (e.g., checking certificate transparency after a domain lookup, or pivoting from a username to linked repositories).

3. **Poor evidence management.** Existing tools rarely maintain structured records of where each piece of information came from, when it was collected, or how confident the system is in its accuracy.

### 1.3 Distinguishing Key Concepts

| Concept | Definition |
|---|---|
| **OSINT Collection** | Raw data acquisition from open sources (DNS queries, WHOIS lookups, API calls) |
| **Correlation** | Cross-referencing data from multiple sources to identify consistency, contradiction, or complementary information |
| **Investigation** | The systematic process of collecting, correlating, and analyzing data to answer an intelligence question |
| **Intelligence** | Synthesized assessment derived from correlated data — interpretation and judgment, not raw data |

### 1.4 Target Users

| User Role | Use Case |
|---|---|
| SOC Analyst | Rapidly pivot from a suspicious indicator to a broader threat picture |
| Threat Intelligence Researcher | Deep-dive investigations into threat actor infrastructure |
| Fraud Investigator | Trace suspicious domains, emails, or usernames across platforms |
| Academic Researcher | Study OSINT methodologies using reproducible investigation workflows |
| Journalist | Investigate online actors using only publicly available information |

### 1.5 What Makes This Different

OSINT Nexus is **not** a chatbot, a static dashboard, or a collection of unrelated OSINT APIs. It is an investigation engine that:
- Automates multi-source collection with standardized adapters
- Normalizes and correlates heterogeneous data
- Maintains full evidence provenance for every observation
- Uses AI to plan investigations and suggest pivots — not to replace analyst judgment

---

## 2. Problem Statement

Investigators conducting OSINT research face a practical workflow problem:

Given a suspicious domain from a phishing alert, an analyst must: (1) query DNS, (2) check WHOIS, (3) search certificate transparency logs, (4) look up the IP address, (5) check threat intelligence, (6) search for related domains, (7) analyze website content, (8) manually correlate results across all sources, (9) decide which leads to follow, (10) repeat the process for each new lead, and (11) document everything with source attribution.

Each step requires a different tool, produces output in a different format, and requires manual correlation. The process is slow, error-prone, and does not scale to complex investigations with multiple pivots.

OSINT Nexus addresses this by providing a unified pipeline: a single target input triggers automated multi-source collection, normalization, entity extraction, relationship detection, correlation, AI-assisted pivot planning, and evidence-backed reporting — all within a single system with a unified knowledge graph.

---

## 3. Project Objectives

| ID | Objective |
|---|---|
| OBJ-01 | Accept and classify investigation targets of multiple types (domain, IP, URL, username, email, organization) |
| OBJ-02 | Collect OSINT data from multiple public sources using modular source adapters |
| OBJ-03 | Normalize heterogeneous source data into a unified internal representation |
| OBJ-04 | Extract entities (domains, IPs, emails, organizations, technologies, etc.) from collected data |
| OBJ-05 | Resolve entities across sources (determine when two records refer to the same entity) |
| OBJ-06 | Detect and record relationships between entities (hosting, registration, certificate, etc.) |
| OBJ-07 | Correlate findings across sources to build a coherent intelligence picture |
| OBJ-08 | Use AI-assisted planning to suggest investigation pivots and identify information gaps |
| OBJ-09 | Maintain full provenance: every observation records its source, timestamp, method, and confidence |
| OBJ-10 | Present findings in an interactive dashboard with knowledge graph, timeline, and evidence panels |
| OBJ-11 | Generate evidence-backed investigation reports |
| OBJ-12 | Prevent uncontrolled API consumption and investigation loops |

---

## 4. Scope

### 4.1 In Scope

| Category | Included |
|---|---|
| Target types | Domain, IP address, URL, email, username/handle, organization/company |
| OSINT sources | DNS, WHOIS/RDAP, certificate transparency, IP/ASN data, search engines, public code repositories, website metadata, technology fingerprinting, public threat intelligence feeds, URL reputation |
| Data processing | Entity extraction, entity resolution, relationship detection, normalization, correlation |
| AI assistance | Investigation pivot planning, entity interpretation, prioritization, summarization |
| Presentation | Knowledge graph, timeline, evidence panel, entity list, investigation log |
| Reporting | Structured reports with source attribution, confidence, and evidence references |

### 4.2 Out of Scope

| Category | Excluded | Reason |
|---|---|---|
| Active exploitation | Port scanning, vulnerability scanning, exploitation | Not OSINT; unauthorized access risk |
| Private data access | Leaked credential databases, private social media, paywalled data | Ethical and legal boundaries |
| Real-time monitoring | Continuous surveillance, live change alerting | Beyond MVP scope |
| Dark web investigation | Tor hidden services, dark web marketplace monitoring | Specialized tooling, legal complexity |
| Social engineering | Impersonation, phishing the target | Unethical and potentially illegal |
| Definitive attribution | Naming specific threat actors | Requires intelligence beyond OSINT |

**Critical constraint:** The system operates only on publicly accessible information and authorized APIs. No unauthorized access, credential theft, exploitation, or bypassing of access controls.

### 4.3 Future Scope

- Phone numbers, cryptocurrency addresses as investigation targets
- Shodan/Censys integration (with API keys)
- Historical DNS and infrastructure migration tracking
- Multi-user collaborative investigation sessions
- STIX/TAXII and MISP export formats
- Plugin SDK for community-contributed source adapters

---

## 5. Supported Investigation Targets

### 5.1 Domain

| Aspect | Details |
|---|---|
| **Input** | `example.com` |
| **Initial OSINT** | DNS records (A, AAAA, MX, NS, TXT), WHOIS/RDAP, Certificate Transparency, HTTP analysis |
| **Possible Pivots** | IP → other hosted domains; NS → other domains on same nameserver; registrant email → other registered domains; subdomains → deeper infrastructure; certificate → other domains on same cert |
| **Useful Relationships** | hosted_on (IP), uses_nameserver, sends_mail_via (MX), registered_by, has_subdomain, covered_by_certificate |

### 5.2 IP Address

| Aspect | Details |
|---|---|
| **Input** | `185.220.100.252` |
| **Initial OSINT** | Reverse DNS, IP-to-ASN mapping, WHOIS (IP allocation), passive DNS, threat intelligence |
| **Possible Pivots** | ASN → other IPs in same ASN; hosted domains → investigate each; PTR record → hostname analysis; threat reports → associated campaigns |
| **Useful Relationships** | belongs_to_asn, operated_by (organization), hosts (domains), has_ptr, associated_with_threat |

### 5.3 URL

| Aspect | Details |
|---|---|
| **Input** | `https://shop.example.com/login.php` |
| **Initial OSINT** | URL parsing, DNS resolution, WHOIS, Certificate Transparency, HTTP response analysis, technology detection, URL reputation |
| **Possible Pivots** | Domain → full domain investigation; embedded links → investigate linked domains; technology → known vulnerabilities |
| **Useful Relationships** | hosted_on (domain), uses_technology, links_to, associated_with_threat |

### 5.4 Username

| Aspect | Details |
|---|---|
| **Input** | `cyberresearcher42` |
| **Initial OSINT** | GitHub/GitLab APIs (profile, repositories, commits), search engines, public forum profiles |
| **Possible Pivots** | Email in commits → email investigation; repositories → technology analysis; linked accounts → cross-platform correlation; organization in profile → organization investigation |
| **Useful Relationships** | has_account_on (platform), owns_repository, associated_with_email, member_of (organization) |

### 5.5 Email

| Aspect | Details |
|---|---|
| **Input** | `admin@secure-hosting.net` |
| **Initial OSINT** | MX analysis, SPF/DKIM/DMARC records, breach exposure check (HIBP), search engines, WHOIS, certificate transparency |
| **Possible Pivots** | Domain (from MX/WHOIS) → domain investigation; mail server IP → IP investigation; associated platforms → username investigation |
| **Useful Relationships** | belongs_to_domain, uses_mail_server, exposed_in (breach), registered_domain, found_in_certificate |

### 5.6 Organization

| Aspect | Details |
|---|---|
| **Input** | `SecureHosting Inc.` |
| **Initial OSINT** | Corporate registries, DNS, Certificate Transparency, search engines, GitHub/GitLab organizations, ASN allocation |
| **Possible Pivots** | Domains → domain investigation; ASN → IP investigation; GitHub org → repository analysis; associated individuals → username/email investigation |
| **Useful Relationships** | owns_domain, operates_asn, has_github, uses_technology, employs (public only) |

---

## 6. Core System Concept

The central idea is that OSINT Nexus should not merely collect data. It should implement a complete intelligence cycle:

```
Input → Collect → Normalize → Extract → Resolve → Correlate →
Plan → Pivot → Collect → Evaluate → Present
```

**Raw data** is a DNS record returning `185.220.100.252`.  
**Intelligence** is the assessment: "This domain was registered 3 days ago, uses bulletproof hosting, and its content mimics a known financial institution — HIGH confidence this is a phishing domain, supported by 5 independent sources."

The system transforms raw observations into intelligence through deterministic processing (normalization, extraction, resolution, correlation) and AI-assisted analysis (planning, prioritization, summarization).

---

## 7. Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│  Investigator enters target: malicious-example.com          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  TARGET CLASSIFICATION                       │
│  Rule-based classifier determines: target_type = domain     │
│  Normalized value: malicious-example.com                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               INVESTIGATION PLANNER                          │
│  Selects initial modules based on target type:              │
│  [DNS, WHOIS, Certificate Transparency, HTTP, Search]       │
│  AI layer may refine priorities based on context             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              INITIAL OSINT COLLECTION                        │
│  Dispatches collection tasks to source adapters:            │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │
│  │ DNS  │ │WHOIS │ │  CT  │ │ HTTP │ │Search│              │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘              │
│     └────────┴────────┴────────┴────────┘                   │
│  Rate limiting, caching, timeout handling, error recovery   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  SOURCE ADAPTERS                             │
│  Each adapter returns a RawResult:                          │
│  - source, adapter version, timestamp                       │
│  - target, query, raw response, status                      │
│  Raw results stored immutably in Evidence DB                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    NORMALIZATION                             │
│  Transform raw data to unified format:                      │
│  - IPs: canonical format                                    │
│  - Domains: lowercase, strip trailing dot                   │
│  - Timestamps: ISO 8601 UTC                                 │
│  - Technologies: normalized names                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 ENTITY EXTRACTION                            │
│  Pattern matching + AI for unstructured text:               │
│  Extracted: domains, IPs, emails, ASNs, certificates,      │
│  technologies, organizations, subdomains                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 ENTITY RESOLUTION                            │
│  Determine when two records = same entity:                  │
│  - Exact match: same normalized value                       │
│  - Foreign key: entity A references entity B                │
│  - Co-occurrence: entities appear together                  │
│  - AI-assisted: semantic similarity for organization names  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               CORRELATION ENGINE                             │
│  Build knowledge graph from entities + relationships:       │
│  - Direct relationships (DNS → IP)                          │
│  - Inferred relationships (shared NS → likely related)      │
│  - Temporal relationships (registered same day)             │
│  - Source corroboration (multiple sources confirm)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           AI-ASSISTED PIVOT SELECTION                       │
│  AI planner evaluates current state:                        │
│  - Identifies information gaps                              │
│  - Recommends high-value pivots with reasoning              │
│  - Estimates API cost and expected value                    │
│  - Checks stopping conditions                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│             ADDITIONAL OSINT COLLECTION                     │
│  Selected pivots trigger new collection tasks               │
│  Same pipeline: adapters → raw → normalize → extract →      │
│  resolve → correlate → graph update                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               EVIDENCE EVALUATION                           │
│  Confidence scoring: source reliability × data quality ×    │
│  corroboration × recency                                    │
│  Contradictions flagged for analyst review                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 KNOWLEDGE GRAPH                              │
│  Central data structure: all entities, relationships,       │
│  confidence scores, evidence references, timestamps         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              INTELLIGENCE ANALYSIS                          │
│  AI-generated: summary, risk assessment, key findings,     │
│  recommended pivots, information gaps                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  DASHBOARD                                  │
│  Interactive display: graph, timeline, evidence panel,      │
│  entity list, AI analysis, activity log                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    REPORT                                    │
│  Evidence-backed PDF/HTML with: executive summary,          │
│  findings, graph, timeline, full evidence table,            │
│  methodology, limitations                                   │
└─────────────────────────────────────────────────────────────┘
```

**Stage explanations:**

**Target Classification** uses deterministic regex rules: contains `@` → email; starts with `http` → URL; contains `.` with valid TLD → domain; matches IPv4 pattern → IP; default → username. Input is normalized (lowercase, validate syntax, extract components).

**Investigation Planner** selects which OSINT modules to activate based on target type. For a domain: DNS, WHOIS, CT, HTTP analysis, search. The AI layer may adjust priorities (e.g., if the domain is on a suspicious TLD, prioritize threat intelligence earlier).

**Source Adapters** execute actual API calls. Each adapter handles authentication (where needed), request construction, response parsing, error handling, retry logic, and rate limit compliance. Failed collections are logged but do not block other collections.

**Normalization** transforms heterogeneous source data into a canonical format. IPs are standardized, domains lowercased, timestamps converted to UTC ISO 8601, technologies matched to known names.

**Entity Extraction** scans normalized data for discrete entities using regex patterns (domains, IPs, emails, ASNs) and AI for unstructured text (organization names from web pages, entity mentions in search snippets).

**Entity Resolution** determines that `EXAMPLE.COM` (WHOIS) and `example.com` (DNS) are the same entity, or that two domains sharing a registrant email are linked. Uses exact matching, normalized matching, foreign key relationships, and AI-assisted semantic matching.

**Correlation Engine** constructs a knowledge graph by connecting entities through detected relationships. Multi-hop paths are discovered (domain → IP → ASN → other domains). Clusters of related infrastructure are identified.

**AI Pivot Selection** analyzes the current knowledge graph, identifies missing information (e.g., "certificate transparency data not yet collected"), ranks potential pivots by expected value, and presents recommendations with reasoning.

**Evidence Evaluation** computes confidence scores: `score = source_reliability × data_quality × corroboration_bonus × recency_factor`. Conflicts between sources are flagged.

---

## 8. System Architecture

### 8.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Dashboard   │  │  Graph View  │  │   Report     │     │
│  │  (React)     │  │  (Cytoscape) │  │   Viewer     │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         └────────────┬────┘──────────────────┘              │
│               ┌──────▼──────┐                                │
│               │  REST API   │                                │
│               └──────┬──────┘                                │
└──────────────────────┼──────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────┐
│               APPLICATION LAYER                              │
│  ┌───────────────────▼──────────────────────────────┐      │
│  │         INVESTIGATION ORCHESTRATOR                │      │
│  │  [Target Classifier] [Planner] [Pivot Controller]│      │
│  │  [Report Generator]  [AI Layer]                   │      │
│  └───────────────────┬──────────────────────────────┘      │
│  ┌───────────────────▼──────────────────────────────┐      │
│  │            PROCESSING PIPELINE                    │      │
│  │  [Normalizer] [Extractor] [Resolver] [Correlator]│      │
│  │  [Confidence Scorer]                             │      │
│  └──────────────────────────────────────────────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────┐
│              COLLECTION LAYER                                │
│  ┌───────────────────▼──────────────────────────────┐      │
│  │         TASK QUEUE (Redis + Worker)               │      │
│  └───────────────────┬──────────────────────────────┘      │
│  ┌───────────────────▼──────────────────────────────┐      │
│  │           OSINT SOURCE ADAPTERS                   │      │
│  │  [DNS] [WHOIS] [CT] [Search] [GitHub] [HTTP]     │      │
│  │  [Threat Intel] [URL Rep] [Tech Detection]       │      │
│  └──────────────────────────────────────────────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────┐
│                DATA LAYER                                    │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │  Graph DB      │  │  Document DB   │  │  Cache       │ │
│  │  (Neo4j)       │  │  (PostgreSQL)  │  │  (Redis)     │ │
│  │  Entities      │  │  Investigations│  │  API Results │ │
│  │  Relationships │  │  Observations  │  │  Sessions    │ │
│  │  Knowledge     │  │  Evidence      │  │              │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Component Architecture

| Component | Technology | Responsibility |
|---|---|---|
| Dashboard | React, TypeScript | Web UI for investigation management |
| Graph Visualization | Cytoscape.js | Interactive knowledge graph rendering |
| REST API | FastAPI (Python) | HTTP API for frontend-backend communication |
| Investigation Orchestrator | Python (asyncio) | Coordinates investigation lifecycle |
| AI Investigation Planner | Python + LLM API | Generates plans, suggests pivots, produces analysis |
| Target Classifier | Python (regex + rules) | Classifies input targets into entity types |
| Task Queue | Celery + Redis | Manages async task execution, rate limiting |
| Data Normalizer | Python | Transforms raw source data to unified format |
| Entity Extractor | Python (regex + spaCy/LLM) | Identifies entities in raw and normalized data |
| Entity Resolver | Python | Deduplicates and merges entity records |
| Correlation Engine | Python + Neo4j Cypher | Builds knowledge graph, discovers relationships |
| Confidence Scorer | Python | Computes confidence scores |
| Source Adapters | Python (one module per source) | Interface to individual OSINT sources |
| Graph Database | Neo4j | Stores entities and relationships |
| Document Store | PostgreSQL | Stores investigations, observations, evidence |
| Cache | Redis | Caches API responses, session data |
| Report Generator | Python + Jinja2 | Generates PDF/HTML reports |

### 8.3 Data Flow Architecture

```
Source Adapter → RawResult (immutable) → Normalizer → NormalizedEntity[]
  → Extractor → Entity[] → Resolver → ResolvedEntity[] → Correlator
  → KnowledgeGraph (Neo4j) → AI Analyzer → IntelligenceReport
```

Each stage produces output consumed by the next. Raw results are never modified after storage. All transformations create new records, preserving the complete data lineage.

---

## 9. OSINT Collection Layer

### 9.1 DNS Module

| Aspect | Details |
|---|---|
| **Collects** | A, AAAA, MX, NS, TXT, SOA, CAA records |
| **Why it matters** | Reveals hosting infrastructure (A/AAAA), email infrastructure (MX), DNS hosting (NS), email security policies (TXT/SPF/DMARC), and authorized CAs (CAA) |
| **Entities created** | Domain, IP, Subdomain, Nameserver (Domain) |
| **Pivots produced** | IP → investigate hosting; NS → find related domains; MX → investigate mail infrastructure; TXT → extract email/SPF data |

### 9.2 WHOIS / RDAP Module

| Aspect | Details |
|---|---|
| **Collects** | Registrant info, registration dates, registrar, domain status, name servers at registration |
| **Why it matters** | Links domains to registrant organizations/emails; newly registered domains are higher risk; registration date establishes timeline |
| **Entities created** | Domain, Organization (registrar/registrant), Email (registrant), Nameserver |
| **Pivots produced** | Registrant email → other domains; registrant org → other domains; registrar → pattern analysis |
| **Limitation** | Many domains use privacy/proxy services, replacing registrant data. System must note "PrivacyGuard" as visible registrant and flag hidden true registrant. |

### 9.3 Certificate Transparency Module

| Aspect | Details |
|---|---|
| **Collects** | Certificates issued to domain (crt.sh API): serial, issuer, validity, SANs |
| **Why it matters** | One of the most reliable subdomain discovery methods. CT logs record every publicly trusted certificate, including for subdomains not in DNS. Reveals infrastructure relationships via shared certificates. |
| **Entities created** | Domain, Subdomain, Certificate, Organization (CA) |
| **Pivots produced** | Subdomains → deeper infrastructure; certificate → other domains on same cert; CA → certificate analysis |

### 9.4 IP / ASN Intelligence Module

| Aspect | Details |
|---|---|
| **Collects** | Reverse DNS (PTR), IP-to-ASN mapping, BGP prefix, hosting organization, country |
| **Why it matters** | Identifies hosting provider; ASN analysis reveals infrastructure sharing; reverse DNS reveals hostname |
| **Entities created** | IP, ASN, Organization (hosting), Hostname (Domain) |
| **Pivots produced** | ASN → other IPs; hosted domains → investigate each; hostname → domain analysis |

### 9.5 Public Search Module

| Aspect | Details |
|---|---|
| **Collects** | Indexed pages, site descriptions, mentions, related sites |
| **Why it matters** | What search engines know about the target; useful for site description and discovering mentions |
| **Entities created** | Domain, URL, Organization (from page content) |
| **Pivots produced** | Related sites → investigate; mentions → discover connections |
| **Limitation** | Search results are algorithmically curated, may not be comprehensive for newly registered domains. |

### 9.6 Public Code Repository Module

| Aspect | Details |
|---|---|
| **Collects** | GitHub/GitLab profiles, repositories, commit history, organization membership |
| **Why it matters** | For username investigations: profile data, email discovery from commits, technology interests, organization links |
| **Entities created** | Username, Email, Repository, Organization, Technology (from repos) |
| **Pivots produced** | Email in commits → email investigation; repos → technology analysis; org membership → org investigation |

### 9.7 Website Metadata / Technology Fingerprinting Module

| Aspect | Details |
|---|---|
| **Collects** | HTTP headers (Server, X-Powered-By), page title, meta tags, script/CSS frameworks, cookie attributes |
| **Why it matters** | Identifies technology stack; page metadata describes site purpose; cookie analysis reveals backend frameworks |
| **Entities created** | Technology, URL (if redirects detected) |
| **Pivots produced** | Technology → known vulnerabilities; redirects → investigate target |

### 9.8 Threat Intelligence Module

| Aspect | Details |
|---|---|
| **Collects** | AbuseIPDB scores/reports, VirusTotal reputation, URLhaus malicious URLs, PhishTank entries, Google Safe Browsing status |
| **Why it matters** | Establishes known malicious reputation; links to documented campaigns |
| **Entities created** | ThreatIndicator |
| **Pivots produced** | Threat reports → associated campaigns; reputation → risk assessment |
| **Limitation** | Threat data may lag behind actual activity; false positives possible. |

### 9.9 Source Availability and Failure Handling

| Concern | Handling |
|---|---|
| API keys required | Some sources (Shodan, VirusTotal) require API keys. If unavailable, adapter is disabled and investigation proceeds with available sources. |
| Rate limits | Each adapter enforces its own rate limit. Exceeding limit causes wait or skip. |
| Service downtime | Failed collections logged as errors, do not block other collections. Investigation continues with partial data. |
| Cached results | If same target + module collected within cache TTL (default 24h), cached result used. |
| Timeout | Each collection task has a timeout (default 30s). Exceeded = failure logged, task skipped. |

---

## 10. Data Normalization

Raw results from different sources are transformed into a unified internal representation.

| Raw Value | Source | Normalized Value |
|---|---|---|
| `192.168.001.001` | DNS | `192.168.1.1` |
| `EXAMPLE.COM.` | WHOIS | `example.com` |
| `Aug 30, 2026` | WHOIS | `2026-08-30T00:00:00Z` |
| `Admin@Example.Com` | CT log | `admin@example.com` |
| `nginx/1.18.0` | HTTP header | `nginx 1.18.0` |
| `AS209103` | BGP | `AS209103` |
| `https://Example.COM/path/` | URL parser | `https://example.com/path/` |

**Normalization rules:**
- IPs: strip leading zeros, canonical IPv4/IPv6 format
- Domains: lowercase, strip trailing dot, punycode decode where applicable
- Timestamps: convert all to ISO 8601 UTC
- Emails: lowercase
- Technologies: match against known name database
- Confidence scores: normalize to 0.0–1.0 scale

**Deduplication:** After normalization, identical values are merged into single entity records. The system tracks which sources provided each piece of data.

---

## 11. Entity Resolution

Entity resolution determines when two observations refer to the same real-world entity.

| Method | Description | Example |
|---|---|---|
| **Exact match** | Identical normalized values | `admin@example.com` = `admin@example.com` |
| **Normalized match** | Different representations, same canonical form | `EXAMPLE.COM` (WHOIS) = `example.com` (DNS) |
| **Foreign key match** | Entity A references Entity B | Domain has A record → IP (direct link) |
| **Co-occurrence** | Entities appear together in records | Email in WHOIS for two domains → links domains |
| **AI-assisted match** | Semantic similarity in names | "SecureHosting Inc." ≈ "Secure Hosting LLC" → likely same |

**Automatic resolution:** Exact matches and normalized matches with high confidence (score ≥ 0.9) are resolved automatically. These are deterministic — the same input always produces the same result.

**Advisory resolution:** AI-assisted matches and co-occurrence matches are **advisory only**. The AI suggests possible entity matches, but the system does not automatically merge ambiguous entities. Advisory matches are presented to the analyst for review and manual confirmation. Every AI suggestion is traceable to the specific observations that support it.

**Important constraint:** A shared relationship does NOT automatically mean identity. Two domains sharing a nameserver may be unrelated (the NS serves thousands of domains). Entity resolution confidence reflects the strength of evidence, not assumption.

**Conflict handling:** When sources disagree, both values are stored as separate observations. The conflict is flagged and presented to the analyst. The AI layer may suggest which value is more likely correct based on source reliability and recency.

---

## 12. Correlation Engine

The correlation engine constructs a knowledge graph from entities and detected relationships.

### 12.1 Relationship Types

| Type | Source → Target | Example |
|---|---|---|
| hosted_on | Domain → IP | `example.com` → `1.2.3.4` |
| uses_nameserver | Domain → NS Domain | `example.com` → `ns1.provider.net` |
| sends_mail_via | Domain → MX Domain | `example.com` → `mail.example.com` |
| registered_by | Domain → Organization/Email | `example.com` → `admin@example.com` |
| has_subdomain | Domain → Subdomain | `example.com` → `shop.example.com` |
| covered_by_certificate | Domain → Certificate | `example.com` → `cert_abc123` |
| belongs_to_asn | IP → ASN | `1.2.3.4` → `AS12345` |
| operates_asn | ASN → Organization | `AS12345` → `HostingCo` |
| owns_repository | Username → Repository | `user1` → `repo1` |
| associated_with_threat | Domain/IP → ThreatIndicator | `evil.com` → `phishing_campaign` |

### 12.2 Correlation Methods

| Method | Description |
|---|---|
| **Direct structural** | DNS records directly link domains to IPs, NS, MX |
| **Infrastructure sharing** | Multiple domains on same IP share hosting |
| **Certificate relationship** | Domains on same certificate may share operator |
| **Temporal** | Domains registered on same day may be coordinated |
| **Source corroboration** | Multiple independent sources confirming same fact |

### 12.3 Confidence Scoring

```
confidence = min(1.0, source_reliability × data_quality × corroboration × recency)
```

| Component | Range | Source |
|---|---|---|
| Source reliability | 0.60–0.95 | Based on source type (DNS=0.95, Search=0.70, etc.) |
| Data quality | 0.7–1.0 | Exact match=1.0, inferred=0.7 |
| Corroboration | 1.0–1.2 | Bonus for multiple independent sources |
| Recency | 0.7–1.0 | Decay based on age of observation |

### 12.4 Example: What a Relationship Means and Does NOT Prove

```
Domain A → hosted_on → IP X ← hosted_on ← Domain B
```

**What this tells us:** Domain A and Domain B are both hosted on IP X. They share the same hosting infrastructure.

**What this does NOT prove:** It does not prove they are operated by the same entity. Shared hosting is common — thousands of unrelated domains may share an IP on a shared hosting platform. Additional evidence (shared registrant, shared certificate, similar content) would be needed to establish common ownership.

---

## 13. Knowledge Graph

### 13.1 Structure

| Element | Description |
|---|---|
| **Nodes** | Entities: Domain, IP, ASN, Email, Username, Organization, Certificate, Technology, ThreatIndicator, URL, Repository |
| **Edges** | Relationships: hosted_on, uses_nameserver, registered_by, has_subdomain, covered_by_certificate, belongs_to_asn, etc. |
| **Node properties** | id, type, value, confidence, first_seen, last_seen, source_count |
| **Edge properties** | id, type, confidence, evidence[], discovered_at, method |
| **Provenance** | Every node and edge links to evidence observations |
| **Temporal** | first_seen, last_seen timestamps on all entities and relationships |

### 13.2 Example Graph 1: Domain Investigation

```
            ┌─────────────────┐
            │ Organization:   │
            │ PrivacyGuard    │
            │ (registrar)     │
            └────────┬────────┘
                     │ registered_with
                     ▼
┌───────────┐   ┌────────────────────────┐   ┌───────────────┐
│ Org:      │   │ Domain:                │   │ Certificate:  │
│ ShadyHost │◄──│ malicious-example.com  │──►│ cert_x1y2z3   │
│ (hosting) │   │ created: 2026-08-28    │   │ Let's Encrypt │
└─────┬─────┘   └──┬───────┬───────┬────┘   └───────────────┘
      │            │       │       │
 operated_by  hosted_on  has_sub  uses_ns
      │            │       │       │
      ▼            ▼       │       ▼
┌───────────┐ ┌────────┐   │  ┌────────────────┐
│ ASN:      │ │ IP:    │   │  │ NS:            │
│ AS209103  │ │185.220 │   │  │ ns1.shadyhost │
│ (Bulletpr)│ │.100.252│   │  │ .net           │
└───────────┘ └───┬────┘   │  └────────────────┘
                  │        │
             hosts other   ▼
             domains   ┌──────────────────────┐
                  │    │ Subdomains:           │
          ┌───────┤    │ shop., login., admin. │
          ▼       ▼    └──────────────────────┘
     ┌─────────┐ ┌─────────┐
     │phishing │ │fake-    │
     │-bank.com│ │login.net│
     └─────────┘ └─────────┘
```

### 13.3 Example Graph 2: Username Investigation

```
┌──────────────────────┐
│ Username:            │
│ cyberresearcher42    │
│ real_name: Alex Chen │
│ email: alex@lab.edu  │
└──┬────────┬────────┬─┘
   │        │        │
   │    has_email  member_of
   │        │        │
   │        ▼        ▼
   │  ┌──────────┐ ┌─────────────────┐
   │  │ Email:   │ │ Organization:   │
   │  │ alex@    │ │ ResearchLab     │
   │  │ lab.edu  │ └─────────────────┘
   │  └──────────┘
   │
   ├── has_account → GitHub
   │                   │
   │              owns_repository
   │                   │
   │            ┌──────┴──────┐
   │            ▼             ▼
   │     ┌──────────┐  ┌──────────────┐
   │     │osint-tool│  │security-     │
   │     │(Python)  │  │scripts (Bash)│
   │     └──────────┘  └──────────────┘
   │
   └── has_account → StackOverflow
                     │
                has_post → [posts about OSINT, cybersecurity]
```

---

## 14. AI Component

### 14.1 Where AI Is Useful

| Task | Why AI Is Appropriate |
|---|---|
| Investigation planning | LLMs can reason about what information is missing and what pivots would be valuable |
| Pivot selection | Evaluating multiple potential pivots and ranking by context-dependent priority |
| Unstructured text interpretation | Extracting entities from natural language (web pages, READMEs, search snippets) |
| Entity matching suggestions | Determining whether "SecureHosting Inc." and "Secure Hosting LLC" are the same entity |
| Relationship explanation | Generating natural language explanations of why a relationship matters |
| Finding prioritization | Ranking findings by relevance and importance in investigation context |
| Summarization | Compressing large volumes of collected data into concise overviews |
| Report generation | Producing prose intelligence reports from structured data |

### 14.2 Where Deterministic Code Must Be Used

| Task | Why Deterministic Code Is Required |
|---|---|
| API calls | Must be exact, reproducible, and error-handled. LLMs cannot reliably construct requests or handle HTTP errors. |
| DNS resolution | Deterministic protocol. Results must be exact, not interpreted. |
| Data validation | Input validation must be consistent and reproducible. |
| Normalization | Must produce identical output for identical input, every time. |
| Graph storage | Database operations must be precise transactions. |
| Evidence preservation | Raw data must be stored exactly as received. LLM interpretation would compromise integrity. |
| Rate limiting | Must be enforced deterministically. LLMs cannot track request counts. |
| Confidence scoring | Mathematical computation, not interpretation. |

### 14.3 Why This Separation Matters

The boundary is clean: **collection and data management are deterministic; analysis and planning are AI-assisted.** The AI layer operates on data that has already been collected, normalized, and validated by deterministic code. This prevents:
- LLM hallucination from corrupting raw evidence
- Non-deterministic API calls failing silently
- Inconsistent normalization breaking entity resolution
- AI-generated data appearing as authoritative source data

---

## 15. AI Investigation Loop

```
┌──────────────────────────────────────────────────────────┐
│ 1. OBSERVE                                               │
│    Execute permitted OSINT collections for current       │
│    target(s). Results stored as raw observations.        │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 2. ANALYZE                                               │
│    Normalize, extract entities, resolve, detect          │
│    relationships, update knowledge graph.                │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 3. IDENTIFY PIVOTS                                       │
│    AI planner evaluates graph state:                     │
│    - What information is missing?                        │
│    - Which entities could yield new information?         │
│    - What is the expected value of each pivot?           │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 4. SCORE AND PRIORITIZE                                  │
│    Rank pivots by: expected information value,           │
│    API cost, risk of redundant collection.               │
│    Check against budget and depth limits.                │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 5. EXECUTE                                               │
│    Dispatch highest-priority permitted action.           │
│    Respects rate limits, budget, depth constraints.      │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 6. COLLECT AND CORRELATE                                 │
│    New observation → normalize → extract → resolve →     │
│    correlate → update graph.                             │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 7. EVALUATE                                              │
│    Update confidence scores. Flag contradictions.        │
│    Assess whether investigation goals are met.           │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────┐
│ 8. REPEAT / TERMINATE                                    │
│    If stopping condition met → produce report.           │
│    Otherwise → return to step 1.                         │
└──────────────────────────────────────────────────────────┘
```

### Stopping Conditions

| Condition | Description |
|---|---|
| Depth limit reached | Maximum pivot rounds executed (configurable: shallow=2, standard=4, deep=6) |
| Budget exhausted | API call budget consumed |
| No viable pivots | AI planner determines no remaining high-value pivots |
| Diminishing returns | Last N rounds produced no new entities or relationships |
| Time limit exceeded | Investigation exceeds maximum duration |
| Analyst termination | Manual stop by investigator |
| Error threshold | Too many consecutive collection failures |

### Preventing Uncontrolled API Calls

| Mechanism | Implementation |
|---|---|
| API budget | Per-investigation maximum API calls (configurable) |
| Per-source rate limiting | Each adapter enforces source-specific limits |
| Concurrency limit | Maximum N concurrent API calls (default 5) |
| Deduplication | Check cache before dispatching identical collection tasks |
| Loop detection | Skip collection if same target + module already collected within TTL |
| Cost estimation | AI planner estimates API cost before dispatching actions |

---

## 16. Evidence and Provenance

### 16.1 Observation Record Structure

Every collected observation stores:

| Field | Description |
|---|---|
| `observation_id` | Unique identifier |
| `investigation_id` | Parent investigation |
| `source_adapter` | Which OSINT module collected this |
| `source_version` | Adapter version |
| `source_url` | API endpoint or query reference |
| `collected_at` | Timestamp (UTC ISO 8601) |
| `method` | Collection method (direct_query, API_call, etc.) |
| `query_parameters` | Exact parameters used |
| `raw_response` | Original, unmodified response from source |
| `normalized_value` | Canonical representation |
| `confidence` | Source reliability × data quality |
| `entities_referenced` | Entity IDs this observation relates to |

### 16.2 Key Principles

| Principle | Implementation |
|---|---|
| Immutability | Raw observation records are append-only. Never modified after creation. |
| Attribution | Every data point in the knowledge graph links to at least one observation. |
| Reproducibility | The exact API call, parameters, and timestamp are recorded. Another investigator can reproduce the collection. |
| AI is not evidence | AI-generated assessments are clearly labeled as analysis, not source data. AI never appears as the source of an observation. |

---

## 17. Investigation Dashboard

### Design Philosophy

The dashboard should be **minimal, professional, analyst-oriented, and information-dense**. No excessive gradients, neon effects, glowing elements, or decorative animations. The UI prioritizes clarity and efficiency over visual spectacle.

### 17.1 Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Header: [Investigation Name] [Status] [Target] [Actions]    │
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│  SIDEBAR   │              MAIN AREA                          │
│            │                                                 │
│ ┌────────┐ │  ┌───────────────────────────────────────────┐ │
│ │Overview│ │  │         KNOWLEDGE GRAPH                   │ │
│ │-Target │ │  │      (Interactive, Zoomable)              │ │
│ │-Status │ │  │                                           │ │
│ │-Stats  │ │  │  [Nodes by type, edges by relationship]   │ │
│ └────────┘ │  └───────────────────────────────────────────┘ │
│            │                                                 │
│ ┌────────┐ │  ┌───────────────────┐ ┌───────────────────┐  │
│ │Entities│ │  │    Timeline       │ │   AI Analysis     │  │
│ │-Domain │ │  │                   │ │   - Summary       │  │
│ │-IP     │ │  │ [Chronological    │ │   - Risk          │  │
│ │-Email  │ │  │  event list]      │ │   - Findings      │  │
│ │-etc.   │ │  │                   │ │   - Pivots        │  │
│ └────────┘ │  └───────────────────┘ └───────────────────┘  │
│            │                                                 │
│ ┌────────┐ ├─────────────────────────────────────────────────┤
│ │Activity│ │           BOTTOM PANEL                          │
│ │Log     │ │  ┌───────────────────────────────────────────┐ │
│ │        │ │  │  Evidence Panel                           │ │
│ │[Event  │ │  │  [Source, timestamp, raw data, conf.]    │ │
│ │ stream]│ │  └───────────────────────────────────────────┘ │
│ └────────┘ │  ┌───────────────────────────────────────────┐ │
│            │  │  Discovered Assets                        │ │
│            │  │  [Subdomains, IPs, Certs, Technologies]   │ │
│            │  └───────────────────────────────────────────┘ │
├────────────┴─────────────────────────────────────────────────┤
│ Footer: [Export Report] [Add Pivot] [Stop Investigation]    │
└──────────────────────────────────────────────────────────────┘
```

### 17.2 Panel Descriptions

| Panel | Purpose | Key Information |
|---|---|---|
| **Overview** | Investigation metadata and status | Target, type, status, depth, API usage, entity/relationship counts, duration |
| **Entity List** | Filterable list of all discovered entities | Grouped by type, each with confidence score. Click to view details. |
| **Knowledge Graph** | Interactive visualization of entity relationships | Nodes sized by connectivity, colored by type. Click nodes/edges for details. Zoom, pan, filter. |
| **Timeline** | Chronological event stream | Collection completions, entity discoveries, pivot actions, errors. Filterable by type. |
| **AI Analysis** | AI-generated intelligence assessment | Summary, risk level, key findings, recommended pivots, information gaps, conflicts. |
| **Evidence Panel** | Detailed source data for selected entity/relationship | Source adapter, timestamp, query, raw response, normalized value, confidence. Expandable evidence chain. |
| **Discovered Assets** | Summary of found infrastructure | Subdomains (count, list), IPs, certificates, technologies, emails. Click to navigate. |
| **Activity Log** | Real-time investigation activity stream | Color-coded (info/success/warning/error), scrollable, filterable. |
| **Reports** | Report generation and export | Generate PDF/HTML report. Preview before export. |

---

## 18. User Workflow

### Example: Domain Investigation

**Step 1: Create Investigation**
- Investigator enters: `shop-login-secure.com`
- Names: "Phishing Campaign - Sept 2026"
- Sets depth: Standard
- Clicks "Start Investigation"

**Step 2: Initial Classification and Collection (automated)**
- Target classified as: domain
- Modules activated: DNS, WHOIS, CT, HTTP, Search

**Step 3: Results Appear (within seconds)**

| Source | Key Findings |
|---|---|
| DNS | A → `185.220.100.252`, NS → `ns1.bulletproof-host.net`, MX → `mail.shop-login-secure.com` |
| WHOIS | Created 2026-08-28, registrar: PrivacyGuard, registrant: REDACTED |
| CT | Certificate issued yesterday by Let's Encrypt. SANs: `admin.`, `login.`, `portal.` subdomains |
| HTTP | Server: nginx, title: "Secure Bank Login", content mimics a known bank |
| Search | 0 results (too new to index) |

**Step 4: AI Analysis**
- Summary: "Domain registered 3 days ago, privacy-protected WHOIS, hosted on known malicious IP (AS209103), content mimics bank login page. HIGH confidence this is phishing infrastructure."
- Recommended pivots: (1) Investigate `185.220.100.252` for other hosted domains, (2) Check threat intel for IP, (3) Investigate `ns1.bulletproof-host.net`

**Step 5: Pivot Execution**
- IP investigation reveals 4 other phishing domains on same IP
- Threat intel: AbuseIPDB score 89/100, 23 abuse reports
- NS investigation reveals 8 additional domains on same nameserver

**Step 6: Correlated Intelligence**
- Knowledge graph shows 13 domains, 1 IP, 1 ASN, 1 NS, 3 subdomains
- Pattern: all domains registered within 7 days, same hosting, same NS → coordinated campaign

**Step 7: Report Generation**
- Investigator clicks "Export Report"
- PDF generated with executive summary, findings, graph, evidence table

---

## 19. Sample Output

### Target
`shop-login-secure.com` — Domain investigation

### Key Findings

| Finding | Confidence | Sources |
|---|---|---|
| Domain registered 3 days ago (2026-08-29) | 0.90 | WHOIS |
| Hosted on 185.220.100.252 (AS209103, Shield Hosting) | 0.95 | DNS, BGP |
| Content mimics known bank login page | 0.85 | HTTP analysis |
| 3 subdomains discovered (admin, login, portal) | 0.95 | Certificate Transparency |
| 4 other phishing domains on same IP | 0.85 | Passive DNS |
| AbuseIPDB score 89/100 | 0.87 | Threat intelligence |
| Certificate issued yesterday by Let's Encrypt | 0.95 | CT log |

### Discovered Entities (18 total)

| Type | Count | Examples |
|---|---|---|
| Domain | 8 | `shop-login-secure.com`, `verify-account-secure.com`, `login-secure-shop.com` |
| Subdomain | 3 | `admin.shop-login-secure.com`, `login.shop-login-secure.com` |
| IP | 1 | `185.220.100.252` |
| ASN | 1 | `AS209103 (Shield Hosting Solutions)` |
| Nameserver | 2 | `ns1.bulletproof-host.net`, `ns2.bulletproof-host.net` |
| Certificate | 1 | `cert_x1y2z3 (Let's Encrypt)` |
| Organization | 2 | `PrivacyGuard LLC`, `Shield Hosting Solutions` |
| Technology | 2 | `nginx 1.18.0`, `PHP 8.1.2` |
| ThreatIndicator | 1 | `phishing_infrastructure` |

### Relationships (22 total)

```
shop-login-secure.com ──hosted_on──► 185.220.100.252
185.220.100.252 ──belongs_to_asn──► AS209103
shop-login-secure.com ──uses_ns──► ns1.bulletproof-host.net
shop-login-secure.com ──has_subdomain──► admin.shop-login-secure.com
shop-login-verify.com ──hosted_on──► 185.220.100.252
login-secure-shop.com ──hosted_on──► 185.220.100.252
```

### Confidence Assessment

**Overall: HIGH (0.90)**

The conclusion that `shop-login-secure.com` is phishing infrastructure is supported by 5 independent sources: DNS, WHOIS, Certificate Transparency, HTTP analysis, and threat intelligence databases (AbuseIPDB, PhishTank).

### Recommended Pivots

| Pivot | Priority | Reasoning |
|---|---|---|
| Investigate `ns1.bulletproof-host.net` | High | May reveal additional campaign domains |
| Investigate registrant email (if privacy removed) | Medium | Could link to other campaigns |
| Monitor certificate transparency for new subdomains | Low | Ongoing monitoring |

### Final Summary

**Shop-login-secure.com** is assessed with high confidence (0.90) to be part of an active phishing campaign targeting financial institution credentials. The domain was registered 3 days ago through a privacy-protecting registrar, is hosted on infrastructure with a documented history of hosting malicious content, and its content mimics a known bank's login page for credential harvesting. Infrastructure analysis reveals 4 additional phishing domains on the same IP and 8 domains on the same nameserver, suggesting a coordinated campaign. All findings are supported by multiple independent sources with full evidence provenance.

---

## 20. Existing Tools and Frameworks

| Tool | Main Strength | Relevant Capability | Difference from OSINT Nexus |
|---|---|---|---|
| **SpiderFoot** | Automated OSINT collection across 200+ modules | Collection breadth | SpiderFoot focuses on module count; Nexus focuses on evidence management, AI-assisted planning, and investigation workflow |
| **Maltego** | Graph-based link analysis and visualization | Entity relationship visualization | Maltego is primarily visualization with manual data gathering; Nexus automates collection with integrated AI planning |
| **Recon-ng** | Modular OSINT reconnaissance framework | Module-based collection | Recon-ng is CLI-focused on raw collection; Nexus adds correlation, graph, AI planning, and dashboard |
| **theHarvester** | Email and subdomain harvesting | Single-purpose collection | Nexus includes this capability as one module within a broader investigation workflow |
| **Amass** | DNS enumeration and attack surface mapping | Deep DNS discovery | Amass focuses on DNS depth; Nexus adds cross-source correlation, evidence management, and AI analysis |
| **MISP** | Threat intelligence sharing and correlation | STIX/TAXII sharing | MISP manages threat intel feeds; Nexus conducts investigations (could export to MISP) |
| **OpenCTI** | Cyber threat intelligence management | CTI platform | OpenCTI manages intel feeds and reports; Nexus generates investigation data |

**No claim of replacement.** OSINT Nexus does not replace these platforms. It occupies a different position: an investigation engine with integrated evidence management, AI-assisted planning, and a unified workflow from target to report.

---

## 21. Research Gap

| Gap | Existing Capability | Limitation | Proposed Contribution |
|---|---|---|---|
| **Fragmented workflows** | Individual OSINT tools collect data effectively | Analysts manually chain tools; data stays in separate silos | Unified pipeline: single input → multi-source collection → normalized output → correlated results |
| **Manual pivot selection** | Experienced analysts identify good pivots | Junior analysts miss pivots; no systematic approach; pivot selection is intuition-based | AI-assisted pivot planning: systematic gap identification, prioritized recommendations with reasoning |
| **Heterogeneous correlation** | Each source provides its own data format | Cross-source correlation is manual; comparing data from different sources is difficult | Automated normalization and correlation engine: unified entity model, automatic relationship detection |
| **Evidence/provenance** | Tools produce results | Results cannot be traced to source; data freshness unknown; reproducibility impossible | Full provenance: every observation records source, timestamp, method, confidence; immutable evidence storage |
| **Investigation planning** | Tools execute what they are told | No systematic reasoning about what to investigate next; no adaptive strategy | AI planner that evaluates investigation state, identifies gaps, recommends actions, prevents redundancy |
| **Explainable AI** | AI/LLM capabilities exist | When AI is used in OSINT tools, reasoning is opaque | Transparent AI: every recommendation includes reasoning; AI operates on deterministic data; analyst retains control |

**Not claimed as novel:** "first AI OSINT tool" — AI tools exist. "completely novel" — this integrates existing capabilities. "no existing system does this" — SpiderFoot, Maltego, and others partially address these gaps.

---

## 22. Project Contribution / Novelty

The contribution is the **engineering integration** of existing capabilities into a cohesive investigation workflow:

| Component | Novelty | Type |
|---|---|---|
| Modular OSINT collection | Low — well-established | Engineering |
| Data normalization | Low — standard data engineering | Engineering |
| Entity extraction and resolution | Low — mature techniques | Engineering |
| Knowledge graph | Low — well-understood | Engineering |
| **Evidence/provenance model** | Medium — underexplored in OSINT tools | Engineering contribution |
| **AI investigation planning** | Medium — emerging application | Research + engineering |
| **Integrated workflow** | Medium — not available in open-source tools | Engineering contribution |

**What can be evaluated experimentally:**
- Entity deduplication accuracy (precision/recall on labeled dataset)
- Relationship detection accuracy
- Pivot recommendation usefulness (analyst study)
- Investigation time reduction compared to manual workflow
- Evidence attribution completeness

---

## 23. Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | System shall accept an investigation target as string input |
| FR-02 | System shall classify target into supported entity type (domain, IP, URL, username, email, organization) |
| FR-03 | System shall collect DNS records (A, AAAA, MX, NS, TXT, SOA) for domain targets |
| FR-04 | System shall perform WHOIS/RDAP lookups for domain and IP targets |
| FR-05 | System shall query Certificate Transparency logs for domain targets |
| FR-06 | System shall resolve IP addresses to ASN and hosting information |
| FR-07 | System shall analyze HTTP responses for technology fingerprinting |
| FR-08 | System shall query GitHub/GitLab APIs for username targets |
| FR-09 | System shall query public threat intelligence feeds (AbuseIPDB, URLhaus) |
| FR-10 | System shall normalize all collected data into unified entity model |
| FR-11 | System shall extract entities from collected data using pattern matching |
| FR-12 | System shall resolve duplicate entities across sources |
| FR-13 | System shall detect and record relationships between entities |
| FR-14 | System shall construct knowledge graph in Neo4j |
| FR-15 | System shall maintain full provenance for every observation |
| FR-16 | System shall compute confidence scores for entities and relationships |
| FR-17 | System shall use AI to suggest investigation pivots with reasoning |
| FR-18 | System shall enforce per-investigation API call budget |
| FR-19 | System shall enforce per-source rate limits |
| FR-20 | System shall support iterative investigation rounds with configurable depth |
| FR-21 | System shall display findings in interactive dashboard |
| FR-22 | System shall visualize knowledge graph with Cytoscape.js |
| FR-23 | System shall generate PDF/HTML investigation reports |
| FR-24 | System shall cache API responses with configurable TTL |
| FR-25 | System shall handle source errors gracefully without blocking investigation |

---

## 24. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Security** | No secrets or credentials in code; API keys in environment variables; no unauthorized data access |
| **Reliability** | Individual source failures do not block investigation; graceful degradation with partial data |
| **Modularity** | New OSINT sources added via adapter interface without modifying core logic |
| **Maintainability** | Code follows consistent style; documented adapter interface; clear component boundaries |
| **Performance** | Initial collection round completes within 60s (5 sources); dashboard loads in < 3s; graph with 100 nodes renders in < 2s |
| **Scalability** | Task queue handles concurrent investigations; database supports multiple simultaneous sessions |
| **Explainability** | Every AI recommendation includes reasoning; every data point links to source evidence |
| **Evidence integrity** | Raw observations immutable after storage; data lineage traceable from graph to original API response |
| **Usability** | Analyst-oriented UI; minimal training required for basic investigations; clear navigation |

---

## 25. MVP

### Target Types (3–5)
1. **Domain** — DNS, WHOIS, Certificate Transparency
2. **IP Address** — Reverse DNS, IP-to-ASN, passive DNS, threat intelligence
3. **Username** — GitHub/GitLab API, search engine

### OSINT Collectors (5–7)
1. DNS adapter
2. WHOIS/RDAP adapter
3. Certificate Transparency adapter
4. IP-to-ASN adapter
5. GitHub API adapter
6. HTTP analysis adapter
7. Threat intelligence adapter (AbuseIPDB)

### Core Features (Phase 6 backend/core-engine checkpoint)
- Target classification and normalization
- Entity extraction and resolution
- Basic correlation engine
- Knowledge graph in Neo4j
- Investigation orchestrator with budget/depth control
- AI-assisted pivot planning
- Basic evidence tracking
- Simple report generation

**Note:** The full interactive dashboard (graph visualization, evidence panel, AI analysis panel) is implemented in Phase 7. The Phase 6 MVP is a functional backend engine with API endpoints. The frontend dashboard is a separate deliverable.

### What Must Work for Success
- Domain investigation produces correlated results with at least 3 source types
- Knowledge graph is queryable via API and returns correct nodes and edges
- Investigation loop runs with budget and depth enforcement
- AI planner suggests pivots with reasoning
- Report generates with source attribution

---

## 26. Implementation Phases

Implementation phases follow `TASKS.md` as the source of truth.

| Phase | Deliverable | Output |
|---|---|---|
| **Phase 1: Scaffolding & Architecture** | Project scaffolding, database schemas, adapter interface, API framework, Docker Compose | Runnable skeleton with all components stubbed |
| **Phase 2: Target Classification & Investigation Management** | Target classifier, investigation CRUD API, investigation list/detail UI | User can create and manage investigations |
| **Phase 3: OSINT Collectors** | DNS, WHOIS, CT, GitHub, HTTP, threat intel adapters | Each adapter returns RawResult; caching and rate limiting enforced |
| **Phase 4: Normalization, Extraction & Resolution** | Data normalizer, entity extractor, entity resolver, relationship detector | Raw results → normalized entities → resolved entities → relationships → confidence scores |
| **Phase 5: Knowledge Graph & Correlation** | Correlation engine, Neo4j integration, graph API | Knowledge graph populated; graph API returns Cytoscape.js-compatible data |
| **Phase 6: Investigation Orchestrator & AI Planner** | Investigation loop, AI planner, pivot selection, budget/depth control | Automated investigation pipeline functional; AI suggests pivots with reasoning |
| **Phase 7: Frontend Dashboard** | React frontend, graph visualization, evidence panel, AI analysis panel | Investigator can interact with investigations via full dashboard UI |
| **Phase 8: Reporting** | Report generator, HTML/PDF/JSON/CSV export | Investigation reports with source attribution generated |
| **Phase 9: Testing, Polish & Documentation** | Unit tests, integration tests, E2E tests, documentation, CI | End-to-end workflow validated; known issues documented |

---

## 27. Evaluation

| Criterion | Metric | Evaluation Method |
|---|---|---|
| OSINT source coverage | % of available sources returning data | Automated: track adapter success rates |
| Entity deduplication accuracy | Precision/recall on labeled entity pairs | Manual: label 100 entity pairs, measure accuracy |
| Relationship detection accuracy | Precision/recall on labeled relationships | Manual: label 50 relationships, compare with system output |
| Pivot recommendation usefulness | Analyst-rated relevance (1–5 scale) | User study: 5 analysts rate 20 pivot recommendations |
| Investigation time reduction | Time to complete investigation vs. manual | Comparative: same investigation completed manually and with tool |
| False relationship rate | Number of incorrect relationships per investigation | Manual review of sample investigation graphs |
| Evidence attribution completeness | % of findings with at least one source linked | Automated: check all graph nodes have evidence |
| System performance | Response time, throughput | Benchmark: 10 concurrent investigations |

**Dataset for evaluation:** Create 10 fictional investigation scenarios with known ground truth (manually verified entity relationships). Use these as test cases for automated and manual evaluation.

---

## 28. Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| API availability | Sources may be down or rate-limited | Graceful degradation; cached results; multiple source fallback |
| Incomplete public data | Not all information is publicly available | Clearly documented scope; system only uses authorized sources |
| False correlations | Shared infrastructure does not mean shared ownership | Confidence scoring; analyst review; correlation explained, not asserted |
| Source reliability | Some sources provide outdated or inaccurate data | Confidence scoring reflects source reliability; recency weighting |
| AI hallucination | LLM may generate plausible but incorrect assessments | AI operates on deterministic data; recommendations labeled as suggestions; analyst retains control |
| Dynamic websites | JavaScript-rendered content may not be captured | HTTP adapter handles basic rendering; noted as limitation |
| Privacy-protected data | WHOIS, social media may be privacy-protected | System notes privacy protection; does not attempt to bypass |
| Legal/ethical constraints | Some OSINT activities may have legal implications | System operates only on public data; ethical guidelines documented |

---

## 29. Ethical and Legal Considerations

**Core principles:**
1. **Public data only.** The system accesses only publicly available information and authorized APIs. No unauthorized access, credential theft, or authentication bypass.
2. **No harm.** The system is designed for defensive investigation, not offensive operations. It does not facilitate harassment, stalking, or unauthorized surveillance.
3. **Transparency.** Every data point is traceable to its source. The system does not obscure its methods.
4. **Analyst control.** AI suggests, the analyst decides. The system does not take autonomous action against targets.
5. **Legal compliance.** Users are responsible for ensuring their investigations comply with applicable laws (CFAA, GDPR, local regulations). The system provides tools for lawful investigation only.
6. **Responsible disclosure.** If investigation reveals active threats, users should follow responsible disclosure practices.

---

## 30. Final Project Summary

### One-line description

OSINT Nexus is an AI-assisted investigation framework that collects, correlates, and presents publicly available intelligence with full evidence provenance.

### 100-word description

OSINT Nexus is a modular OSINT investigation framework for cybersecurity analysts and researchers. Given an investigation target (domain, IP, URL, username, email, or organization), it automatically collects data from public sources (DNS, WHOIS, certificate transparency, threat intelligence, code repositories), normalizes heterogeneous data into a unified entity model, extracts and resolves entities, detects relationships, constructs a knowledge graph, and uses AI-assisted planning to suggest investigation pivots. Every observation retains full source attribution, timestamps, and confidence scoring. The system presents findings in an interactive dashboard with graph visualization and generates evidence-backed reports. It operates exclusively on publicly available information.

### Technical summary

**Stack:** Python (backend), React (frontend), Neo4j (graph DB), PostgreSQL (document store), Redis (cache/queue), Celery (task queue), Cytoscape.js (graph visualization), LLM API (AI layer)

**Architecture:** Modular adapter-based collection → deterministic normalization/extraction/resolution → graph-based correlation → AI-assisted planning → interactive dashboard → evidence-backed reporting

**Key design decisions:** Evidence immutability, deterministic data pipeline, AI operates on processed data only, analyst retains control, source attribution on every finding

---

*End of specification.*
