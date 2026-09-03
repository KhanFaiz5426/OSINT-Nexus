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
  if (kind === "activity") return <Activity className="h-3.5 w-3.5" />;
  return <Database className="h-3.5 w-3.5" />;
}

function badgeColor(kind: string): string {
  const k = kind.toLowerCase();
  if (k.includes("error") || k.includes("fail")) {
    return "bg-red-50 text-red-700 ring-red-200";
  }
  if (k.includes("complete") || k.includes("stopped")) {
    return "bg-green-50 text-green-700 ring-green-200";
  }
  if (k.includes("start") || k.includes("pivot")) {
    return "bg-blue-50 text-blue-700 ring-blue-200";
  }
  if (k.includes("investigation")) {
    return "bg-purple-50 text-purple-700 ring-purple-200";
  }
  return "bg-gray-100 text-gray-700 ring-gray-200";
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
      <ol className="divide-y divide-gray-100">
        {entries.map((e) => (
          <li key={e.id} className="flex gap-2 px-3 py-2">
            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500">
              {eventIcon(e.kind)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${badgeColor(
                    e.badge ?? "",
                  )}`}
                >
                  {e.badge}
                </span>
                <span className="shrink-0 text-[10px] text-gray-400">
                  {formatRelativeTime(e.timestamp)}
                </span>
              </div>
              <div className="mt-1 truncate text-xs font-medium text-gray-900">
                {e.title}
              </div>
              {e.detail && (
                <div className="truncate text-[11px] text-gray-500">
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
