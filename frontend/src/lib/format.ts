/**
 * Shared formatting and display helpers.
 * Adapted for the dark-first OSINT Nexus theme.
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

/** Status badge classes for light and dark backgrounds. */
export function statusBadgeClass(status: InvestigationStatus): string {
  switch (status) {
    case "running":
      return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30";
    case "completed":
      return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30";
    case "error":
      return "bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30";
    case "stopped":
      return "bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/30";
    case "paused":
      return "bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/30";
    case "created":
      return "bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/30";
  }
}

/** Risk level badge classes for light and dark backgrounds. */
export function riskBadgeClass(level: RiskLevel): string {
  switch (level) {
    case "low":
      return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30";
    case "medium":
      return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30";
    case "high":
      return "bg-orange-500/15 text-orange-600 dark:text-orange-400 border border-orange-500/30";
    case "critical":
      return "bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30";
  }
}

/** Confidence text color for light and dark backgrounds. */
export function confidenceBadgeClass(c: number): string {
  if (c >= 0.8) return "text-emerald-600 dark:text-emerald-400";
  if (c >= 0.5) return "text-amber-600 dark:text-amber-400";
  if (c > 0) return "text-orange-600 dark:text-orange-400";
  return "text-slate-600 dark:text-slate-400";
}

/**
 * Entity type color tokens for dark backgrounds.
 */
export function entityTypeColor(type: string): {
  bg: string;
  text: string;
  ring: string;
} {
  const t = type.toLowerCase();
  if (t.includes("threat")) {
    return {
      bg: "bg-red-500/15",
      text: "text-red-400",
      ring: "ring-red-500/30",
    };
  }
  if (t.includes("ip") || t.includes("asn")) {
    return {
      bg: "bg-indigo-500/15",
      text: "text-indigo-400",
      ring: "ring-indigo-500/30",
    };
  }
  if (t.includes("domain") || t.includes("subdomain")) {
    return {
      bg: "bg-sky-500/15",
      text: "text-sky-400",
      ring: "ring-sky-500/30",
    };
  }
  if (t.includes("email") || t.includes("person")) {
    return {
      bg: "bg-purple-500/15",
      text: "text-purple-400",
      ring: "ring-purple-500/30",
    };
  }
  if (t.includes("certificate")) {
    return {
      bg: "bg-emerald-500/15",
      text: "text-emerald-400",
      ring: "ring-emerald-500/30",
    };
  }
  if (t.includes("url")) {
    return {
      bg: "bg-cyan-500/15",
      text: "text-cyan-400",
      ring: "ring-cyan-500/30",
    };
  }
  if (t.includes("username") || t.includes("repository")) {
    return {
      bg: "bg-amber-500/15",
      text: "text-amber-400",
      ring: "ring-amber-500/30",
    };
  }
  if (t.includes("technology")) {
    return {
      bg: "bg-slate-500/15",
      text: "text-slate-400",
      ring: "ring-slate-500/30",
    };
  }
  if (t.includes("organization")) {
    return {
      bg: "bg-rose-500/15",
      text: "text-rose-400",
      ring: "ring-rose-500/30",
    };
  }
  return {
    bg: "bg-slate-500/15",
    text: "text-slate-400",
    ring: "ring-slate-500/30",
  };
}

/**
 * Cytoscape node type colors — brighter variants for dark canvas.
 */
export const NODE_TYPE_COLORS: Record<string, string> = {
  Domain: "#38bdf8",
  Subdomain: "#7dd3fc",
  IP: "#818cf8",
  ASN: "#a78bfa",
  Certificate: "#34d399",
  Email: "#c084fc",
  URL: "#22d3ee",
  Username: "#fbbf24",
  Repository: "#f59e0b",
  Technology: "#94a3b8",
  Organization: "#fb7185",
  Person: "#e879f9",
  ThreatIndicator: "#f87171",
};

export const DEFAULT_NODE_COLOR = "#64748b";
export const DEFAULT_EDGE_COLOR = "#475569";
