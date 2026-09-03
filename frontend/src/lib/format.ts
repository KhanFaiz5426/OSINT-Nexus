/**
 * Shared formatting and display helpers.
 */

import type { InvestigationStatus, RiskLevel } from "../api/investigations";

export function formatDateTime(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatRelativeTime(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso).getTime();
    if (Number.isNaN(d)) return iso;
    const diff = Date.now() - d;
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.floor(hr / 24);
    if (day < 7) return `${day}d ago`;
    return formatDate(iso);
  } catch {
    return iso;
  }
}

export function formatPercent(v: number, digits = 0): string {
  if (!Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function statusBadgeClass(status: InvestigationStatus): string {
  switch (status) {
    case "running":
      return "bg-yellow-50 text-yellow-800 ring-1 ring-yellow-200";
    case "completed":
      return "bg-green-50 text-green-800 ring-1 ring-green-200";
    case "error":
      return "bg-red-50 text-red-800 ring-1 ring-red-200";
    case "stopped":
      return "bg-gray-100 text-gray-700 ring-1 ring-gray-200";
    case "paused":
      return "bg-orange-50 text-orange-800 ring-1 ring-orange-200";
    case "created":
      return "bg-blue-50 text-blue-800 ring-1 ring-blue-200";
  }
}

export function riskBadgeClass(level: RiskLevel): string {
  switch (level) {
    case "low":
      return "bg-green-50 text-green-800 ring-1 ring-green-200";
    case "medium":
      return "bg-yellow-50 text-yellow-800 ring-1 ring-yellow-200";
    case "high":
      return "bg-orange-50 text-orange-800 ring-1 ring-orange-200";
    case "critical":
      return "bg-red-50 text-red-800 ring-1 ring-red-200";
  }
}

export function confidenceBadgeClass(c: number): string {
  if (c >= 0.8) return "text-green-700";
  if (c >= 0.5) return "text-yellow-700";
  if (c > 0) return "text-orange-700";
  return "text-gray-500";
}

/**
 * Type color tokens for entities. Returns a Tailwind text/ring combo.
 * Values come from the backend's EntityType enum.
 */
export function entityTypeColor(type: string): {
  bg: string;
  text: string;
  ring: string;
} {
  const t = type.toLowerCase();
  if (t.includes("threat")) {
    return {
      bg: "bg-red-100",
      text: "text-red-800",
      ring: "ring-red-300",
    };
  }
  if (t.includes("ip") || t.includes("asn")) {
    return {
      bg: "bg-indigo-100",
      text: "text-indigo-800",
      ring: "ring-indigo-300",
    };
  }
  if (t.includes("domain") || t.includes("subdomain")) {
    return {
      bg: "bg-blue-100",
      text: "text-blue-800",
      ring: "ring-blue-300",
    };
  }
  if (t.includes("email") || t.includes("person")) {
    return {
      bg: "bg-purple-100",
      text: "text-purple-800",
      ring: "ring-purple-300",
    };
  }
  if (t.includes("certificate")) {
    return {
      bg: "bg-emerald-100",
      text: "text-emerald-800",
      ring: "ring-emerald-300",
    };
  }
  if (t.includes("url")) {
    return {
      bg: "bg-cyan-100",
      text: "text-cyan-800",
      ring: "ring-cyan-300",
    };
  }
  if (t.includes("username") || t.includes("repository")) {
    return {
      bg: "bg-amber-100",
      text: "text-amber-800",
      ring: "ring-amber-300",
    };
  }
  if (t.includes("technology")) {
    return {
      bg: "bg-slate-100",
      text: "text-slate-800",
      ring: "ring-slate-300",
    };
  }
  if (t.includes("organization")) {
    return {
      bg: "bg-rose-100",
      text: "text-rose-800",
      ring: "ring-rose-300",
    };
  }
  return {
    bg: "bg-gray-100",
    text: "text-gray-800",
    ring: "ring-gray-300",
  };
}

/**
 * Build a Cytoscape.js style selector mapping for node type colors.
 * Values are flat strings (no rgba) for clarity.
 */
export const NODE_TYPE_COLORS: Record<string, string> = {
  Domain: "#1d4ed8",
  Subdomain: "#3b82f6",
  IP: "#6366f1",
  ASN: "#4f46e5",
  Certificate: "#059669",
  Email: "#7c3aed",
  URL: "#0891b2",
  Username: "#b45309",
  Repository: "#92400e",
  Technology: "#475569",
  Organization: "#be123c",
  Person: "#a21caf",
  ThreatIndicator: "#dc2626",
};

export const DEFAULT_NODE_COLOR = "#6b7280";
export const DEFAULT_EDGE_COLOR = "#9ca3af";
