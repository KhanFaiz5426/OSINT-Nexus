/**
 * Frontend API client for OSINT Nexus workspace management.
 *
 * Wraps the existing backend workspace endpoints:
 *   GET  /api/v1/workspace/status
 *   POST /api/v1/workspace/new
 *   POST /api/v1/workspace/open
 *   POST /api/v1/workspace/save-as
 *   POST /api/v1/workspace/close
 *
 * Follows the same conventions as investigations.ts.
 */

import { ApiError } from "./investigations";

const API_BASE = "/api/v1";

// ── Types ───────────────────────────────────────────────────────────────────

export interface WorkspaceStatus {
  active_workspace: string | null;
}

export interface WorkspacePathRequest {
  path: string;
}

// ── HTTP helper (mirrors investigations.ts) ─────────────────────────────────

async function http<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${API_BASE}${path}`;

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

// ── Workspace API ───────────────────────────────────────────────────────────

export const workspaceApi = {
  /** Get the currently active workspace path. */
  status: () => http<WorkspaceStatus>("/workspace/status"),

  /** Create a new workspace at the given path. */
  create: (path: string) =>
    http<WorkspaceStatus>("/workspace/new", {
      method: "POST",
      body: JSON.stringify({ path } satisfies WorkspacePathRequest),
    }),

  /** Open an existing .osint workspace file. */
  open: (path: string) =>
    http<WorkspaceStatus>("/workspace/open", {
      method: "POST",
      body: JSON.stringify({ path } satisfies WorkspacePathRequest),
    }),

  /** Save a snapshot of the active workspace to a new file. */
  saveAs: (path: string) =>
    http<WorkspaceStatus>("/workspace/save-as", {
      method: "POST",
      body: JSON.stringify({ path } satisfies WorkspacePathRequest),
    }),

  /** Close the current workspace safely. */
  close: () =>
    http<WorkspaceStatus>("/workspace/close", {
      method: "POST",
    }),

  /** Generate a report in the specified format. */
  generateReport: (format: "html" | "json" | "csv" | "stix") =>
    http<any>("/workspace/reports", {
      method: "POST",
      body: JSON.stringify({ format }),
    }),

  /** Get the download URL for a generated report. */
  downloadUrl: (reportId: string) =>
    `${API_BASE}/workspace/reports/${reportId}/download`,

  downloadReportUrl: (reportId: string) =>
    `${API_BASE}/workspace/reports/${reportId}/download`,
};
