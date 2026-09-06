import { Activity, Database, Network } from "lucide-react";
import { useActivity, useObservations } from "../hooks/useApi";
import { Panel } from "./Panel";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { formatRelativeTime } from "../lib/format";

type EventKind = "activity" | "observation";

interface TimelineEntry {
  id: string;
  kind: EventKind;
  timestamp: string;
  title: string;
  detail?: string;
  badge?: string;
}

function eventIcon(kind: EventKind) {
  if (kind === "activity") return <Activity className="h-3 w-3" />;
  return <Database className="h-3 w-3" />;
}

function badgeColor(kind: string): string {
  const k = kind.toLowerCase();
  if (k.includes("error") || k.includes("fail")) {
    return "bg-red-500/15 text-red-400 border border-red-500/25";
  }
  if (k.includes("complete") || k.includes("stopped")) {
    return "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25";
  }
  if (k.includes("start") || k.includes("pivot")) {
    return "bg-sky-500/15 text-sky-400 border border-sky-500/25";
  }
  if (k.includes("investigation")) {
    return "bg-purple-500/15 text-purple-400 border border-purple-500/25";
  }
  return "bg-slate-500/15 text-slate-400 border border-slate-500/25";
}

export function TimelinePanel({
  investigationId,
}: {
  investigationId: string;
}) {
  const activity = useActivity(investigationId, { limit: 50 });
  const observations = useObservations(investigationId, { limit: 50 });

  const isLoading = activity.isLoading || observations.isLoading;
  const hasError = activity.error && observations.error;

  if (hasError) {
    return (
      <Panel title="Timeline">
        <ErrorState message="Failed to load timeline." />
      </Panel>
    );
  }

  const entries: TimelineEntry[] = [];

  if (activity.data) {
    for (const a of activity.data.items) {
      const detailParts: string[] = [];
      const d = a.details ?? {};
      if (typeof d.target === "string") detailParts.push(`target: ${d.target}`);
      if (typeof d.stop_reason === "string")
        detailParts.push(`reason: ${d.stop_reason}`);
      if (typeof d.error === "string") detailParts.push(`error: ${d.error}`);
      if (typeof d.pivots_dispatched === "number")
        detailParts.push(`${d.pivots_dispatched} pivots`);
      if (typeof d.observations_collected === "number")
        detailParts.push(`${d.observations_collected} observations`);
      entries.push({
        id: `a-${a.id}`,
        kind: "activity",
        timestamp: a.created_at,
        title: a.event_type.replace(/_/g, " "),
        detail: detailParts.join(" · ") || undefined,
        badge: a.event_type,
      });
    }
  }

  if (observations.data) {
    for (const o of observations.data.items) {
      entries.push({
        id: `o-${o.id}`,
        kind: "observation",
        timestamp: o.collected_at,
        title: `${o.source_adapter} → ${o.target}`,
        detail: o.method || undefined,
        badge: o.source_adapter,
      });
    }
  }

  entries.sort((a, b) => {
    const ta = new Date(a.timestamp).getTime();
    const tb = new Date(b.timestamp).getTime();
    return tb - ta;
  });

  if (isLoading && entries.length === 0) {
    return (
      <Panel title="Timeline">
        <LoadingState label="Loading timeline..." rows={3} />
      </Panel>
    );
  }

  if (entries.length === 0) {
    return (
      <Panel title="Timeline">
        <EmptyState
          icon={<Network className="h-10 w-10" />}
          title="No activity yet"
          description="Investigation events and observations will appear here."
        />
      </Panel>
    );
  }

  return (
    <Panel title="Timeline" bodyClassName="p-0">
      <ol className="divide-y divide-[var(--nx-border-subtle)]">
        {entries.map((e) => (
          <li key={e.id} className="flex gap-2 px-3 py-2">
            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--nx-surface-3)] text-[var(--nx-text-muted)]">
              {eventIcon(e.kind)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${badgeColor(
                    e.badge ?? "",
                  )}`}
                >
                  {e.badge}
                </span>
                <span className="shrink-0 text-[10px] font-mono text-[var(--nx-text-muted)]">
                  {formatRelativeTime(e.timestamp)}
                </span>
              </div>
              <div className="mt-1 truncate text-xs font-medium text-[var(--nx-text-secondary)]">
                {e.title}
              </div>
              {e.detail && (
                <div className="truncate text-[11px] text-[var(--nx-text-muted)]">
                  {e.detail}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
