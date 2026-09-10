/**
 * Frontend API client for OSINT Nexus backend.
 *
 * All endpoints are under `/api/v1`. The Vite dev server proxies these
 * to the FastAPI backend on port 8000.
 *
 * SECURITY: This module treats every response as untrusted. Values are
 * not interpolated into HTML; React escapes strings by default. Never
 * use `dangerouslySetInnerHTML` on API data.
 */

const API_BASE = "/api/v1";

// ── Shared types ────────────────────────────────────────────────────────────

export type TargetType =
  | "domain"
  | "ip"
  | "url"
  | "email"
  | "username"
  | "organization"
  | "unknown";

export type InvestigationStatus =
  | "created"
  | "running"
  | "paused"
  | "completed"
  | "stopped"
  | "error";

export type InvestigationDepth = "shallow" | "standard" | "deep";

export type EntityType =
  | "Person"
  | "Organization"
  | "Domain"
  | "Subdomain"
  | "IP"
  | "ASN"
  | "Certificate"
  | "URL"
  | "Email"
  | "Username"
  | "Repository"
  | "Technology"
  | "ThreatIndicator";

export type RelationshipType =
  | "hosted_on"
  | "uses_nameserver"
  | "sends_mail_via"
  | "registered_by"
  | "registered_with"
  | "has_subdomain"
  | "covered_by_certificate"
  | "issued_by"
  | "belongs_to_asn"
  | "operated_by"
  | "has_ptr"
  | "owns_repository"
  | "has_account_on"
  | "associated_with_email"
  | "member_of"
  | "uses_technology"
  | "links_to"
  | "associated_with_threat"
  | "co_occurs_with";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type SourceAvailabilityStatus =
  | "available"
  | "not_found"
  | "redirected"
  | "access_denied"
  | "auth_required"
  | "rate_limited"
  | "temporarily_unavailable"
  | "blocked"
  | "unknown";

export interface SourceAvailability {
  url: string;
  status: SourceAvailabilityStatus;
  checked_at: string;
  detail: string;
  final_url: string;
}

// ── Investigation ───────────────────────────────────────────────────────────

export interface Investigation {
  id: string;
  name: string;
  target: string;
  target_type: TargetType;
  status: InvestigationStatus;
  depth: InvestigationDepth;
  created_at: string;
  updated_at: string;
  entity_count: number;
  relationship_count: number;
  observation_count: number;
}

export interface InvestigationCreate {
  name: string;
  target: string;
  depth?: InvestigationDepth;
}

export interface InvestigationStatusDetail {
  id: string;
  status: InvestigationStatus;
  target: string;
  target_type: TargetType;
  depth: InvestigationDepth;
  api_calls_used: number;
  api_budget: number;
  entity_count: number;
  relationship_count: number;
  created_at: string;
  updated_at: string;
}

export interface InvestigationStartResponse {
  message: string;
  investigation_id: string;
  task_id: string;
}

// ── Entity / Relationship ────────────────────────────────────────────────────

export interface Entity {
  id: string;
  investigation_id: string;
  type: EntityType;
  value: string;
  confidence: number;
  first_seen: string | null;
  last_seen: string | null;
  source_count: number;
  sources?: string[];
  properties: Record<string, unknown>;
}

export interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  type: RelationshipType;
  confidence: number;
  evidence: string[];
  discovered_at: string | null;
  method: string;
}

// ── Observations (raw evidence) ──────────────────────────────────────────────

export interface Observation {
  id: string;
  source_adapter: string;
  source_version: string;
  collected_at: string;
  method: string;
  target: string;
  raw_response: Record<string, unknown>;
  normalized_value: string;
  confidence: number;
  status: string;
}

// ── Knowledge Graph ──────────────────────────────────────────────────────────

export interface GraphNode {
  data: {
    id: string;
    label: string;
    type: string;
    confidence: number;
    first_seen?: string;
    last_seen?: string;
    source_count?: number;
    properties?: Record<string, unknown>;
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    relationship_type: string;
    confidence: number;
    evidence?: string[];
    discovered_at?: string;
    method?: string;
  };
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── Activity / Timeline ──────────────────────────────────────────────────────

export interface ActivityItem {
  id: number;
  event_type: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ActivityResponse {
  items: ActivityItem[];
  limit: number;
  offset: number;
}

export interface ObservationResponse {
  items: Observation[];
  limit: number;
  offset: number;
}

// ── AI Analysis ──────────────────────────────────────────────────────────────

export interface KeyFinding {
  title: string;
  description: string;
  entity_ids: string[];
  confidence: number;
}

export interface AnalyzerOutput {
  summary: string;
  risk_level: RiskLevel;
  risk_reasoning: string;
  key_findings: KeyFinding[];
  recommendations: string[];
}

export interface GraphSummary {
  entity_count: number;
  relationship_count: number;
  entity_summary: Array<{
    type: string;
    value: string;
    confidence: number;
    source_count: number;
    id: string;
  }>;
  relationship_summary: Array<{
    source: string;
    target: string;
    type: string;
    confidence: number;
  }>;
}

export interface AIAnalysis {
  investigation_id: string;
  analyzer_output: AnalyzerOutput | null;
  graph_summary: GraphSummary;
  pivot_rounds_completed: number;
  generated_at: string;
}

// ── HTTP helper ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function http<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string | number | undefined> },
): Promise<T> {
  let url = `${API_BASE}${path}`;
  if (init?.params) {
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(init.params)) {
      if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
    }
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail))
        detail = body.detail.map((e: { msg?: string }) => e.msg ?? "").join("; ");
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Investigations ──────────────────────────────────────────────────────────

export const investigationsApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    http<Investigation[]>("/investigations", { params }),
  get: (id: string) => http<Investigation>(`/investigations/${id}`),
  create: (data: InvestigationCreate) =>
    http<Investigation>("/investigations", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  stop: (id: string) =>
    http<Investigation>(`/investigations/${id}/stop`, { method: "POST" }),
  delete: (id: string) =>
    http<{ message: string }>(`/investigations/${id}`, { method: "DELETE" }),
  status: (id: string) =>
    http<InvestigationStatusDetail>(`/investigations/${id}/status`),
  start: (id: string) =>
    http<InvestigationStartResponse>(`/investigations/${id}/start`, {
      method: "POST",
    }),
};

// ── Graph ────────────────────────────────────────────────────────────────────

export const graphApi = {
  subgraph: (
    investigationId: string,
    params?: { entity_id?: string; depth?: number },
  ) =>
    http<GraphResponse>(`/investigations/${investigationId}/graph`, { params }),
  paths: (
    investigationId: string,
    params: { source_id: string; target_id: string; max_hops?: number },
  ) =>
    http<GraphResponse>(`/investigations/${investigationId}/graph/paths`, {
      params,
    }),
};

// ── Entity AI Analysis ───────────────────────────────────────────────────────

export interface EntityAIAnalysis {
  entity_id: string;
  entity_type: string;
  entity_value: string;
  entity_confidence: number;
  investigation_target: string;
  investigation_target_type: string;
  analysis: {
    what_is: string;
    key_information: string[];
    evidence_summary: string;
    confidence_assessment: string;
    connection_to_target: string;
    significance: string;
    uncertainties: string[];
    ai_inferences: string[];
  };
  confirmed_facts: Array<{
    fact: string;
    source: string;
    confidence: number;
    collected_at: string;
  }>;
  evidence_count: number;
  relationship_count: number;
  related_entities: Array<{
    id: string;
    type: string;
    label: string;
  }>;
  generated_at: string;
}

// ── Entities ─────────────────────────────────────────────────────────────────

export const entitiesApi = {
  get: (id: string, investigationId: string) =>
    http<Entity>(`/entities/${encodeURIComponent(id)}`, {
      params: { investigation_id: investigationId },
    }),
  evidence: (id: string, investigationId: string) =>
    http<Observation[]>(`/entities/${encodeURIComponent(id)}/evidence`, {
      params: { investigation_id: investigationId },
    }),
  relationships: (id: string, investigationId: string) =>
    http<Relationship[]>(`/entities/${encodeURIComponent(id)}/relationships`, {
      params: { investigation_id: investigationId },
    }),
  aiAnalysis: (id: string, investigationId: string) =>
    http<EntityAIAnalysis>(`/entities/${encodeURIComponent(id)}/ai-analysis`, {
      params: { investigation_id: investigationId },
    }),
  sourceAvailability: (id: string, investigationId: string) =>
    http<SourceAvailability>(`/entities/${encodeURIComponent(id)}/source-availability`, {
      params: { investigation_id: investigationId },
    }),
};

// ── Activity / Observations ─────────────────────────────────────────────────

export const activityApi = {
  list: (investigationId: string, params?: { limit?: number; offset?: number }) =>
    http<ActivityResponse>(`/investigations/${investigationId}/activity`, {
      params,
    }),
  observations: (
    investigationId: string,
    params?: { limit?: number; offset?: number },
  ) =>
    http<ObservationResponse>(
      `/investigations/${investigationId}/observations`,
      { params },
    ),
};

// ── AI ───────────────────────────────────────────────────────────────────────

export const aiApi = {
  analysis: (investigationId: string) =>
    http<AIAnalysis>(`/investigations/${investigationId}/ai-analysis`),
};

// ── Reports ─────────────────────────────────────────────────────────────────

export type ReportFormat = "html" | "pdf" | "json" | "csv";

export interface Report {
  id: string;
  investigation_id: string;
  format: ReportFormat;
  created_at: string;
  download_url: string;
  file_size: number;
}

export interface ReportGenerateRequest {
  format: ReportFormat;
}

export const reportsApi = {
  list: (investigationId: string) =>
    http<Report[]>(`/investigations/${investigationId}/reports`),
  get: (investigationId: string, reportId: string) =>
    http<Report>(`/investigations/${investigationId}/reports/${reportId}`),
  generate: (investigationId: string, data: ReportGenerateRequest) =>
    http<Report>(`/investigations/${investigationId}/reports`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  downloadUrl: (investigationId: string, reportId: string) =>
    `${API_BASE}/investigations/${investigationId}/reports/${reportId}/download`,
};
