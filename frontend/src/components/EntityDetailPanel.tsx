import { useState } from "react";
import { ChevronRight, ChevronLeft, Link2, X } from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { Panel } from "./Panel";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import {
  useEntity,
  useEntityEvidence,
  useEntityRelationships,
  useInvestigationGraph,
} from "../hooks/useApi";
import {
  confidenceBadgeClass,
  entityTypeColor,
  formatDateTime,
  formatPercent,
} from "../lib/format";
import { cn } from "../lib/utils";

export function EntityDetailPanel({
  investigationId,
}: {
  investigationId: string;
}) {
  const selectedEntityId = useWorkspaceStore((s) => s.selectedEntityId);
  const selectEntity = useWorkspaceStore((s) => s.selectEntity);
  const rightPanelOpen = useWorkspaceStore((s) => s.rightPanelOpen);
  const setRightPanel = useWorkspaceStore((s) => s.setRightPanel);

  const entity = useEntity(selectedEntityId ?? undefined, investigationId);
  const evidence = useEntityEvidence(
    selectedEntityId ?? undefined,
    investigationId,
  );
  const relationships = useEntityRelationships(
    selectedEntityId ?? undefined,
    investigationId,
  );
  const { data: graph } = useInvestigationGraph(investigationId);

  const [evidenceOpen, setEvidenceOpen] = useState<Record<string, boolean>>(
    {},
  );
  const [tab, setTab] = useState<"overview" | "evidence" | "relationships">(
    "overview",
  );

  if (!rightPanelOpen) {
    return (
      <button
        onClick={() => setRightPanel(true)}
        className="absolute right-3 top-3 z-10 inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 shadow hover:bg-gray-50"
      >
        <ChevronLeft className="h-3 w-3" /> Entity
      </button>
    );
  }

  return (
    <Panel
      title={
        selectedEntityId ? (
          <span className="flex items-center gap-2">
            <span>Entity</span>
            <span className="font-mono text-xs normal-case text-gray-500">
              {selectedEntityId.split(":").slice(1).join(":") || selectedEntityId}
            </span>
          </span>
        ) : (
          "Entity Inspector"
        )
      }
      actions={
        selectedEntityId && (
          <button
            onClick={() => selectEntity(null)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close entity panel"
          >
            <X className="h-4 w-4" />
          </button>
        )
      }
      bodyClassName="p-0"
    >
      {!selectedEntityId && (
        <EmptyState
          title="No entity selected"
          description="Click any row in the entity list or any node in the graph to inspect details here."
        />
      )}

      {selectedEntityId && entity.isLoading && <LoadingState rows={4} />}
      {selectedEntityId && entity.error && (
        <div className="p-4">
          <ErrorState message="Failed to load entity." />
        </div>
      )}

      {selectedEntityId && entity.data && (
        <div className="flex h-full flex-col">
          <div className="border-b border-gray-200 px-4 py-3">
            <div className="flex items-center gap-2">
              {(() => {
                const color = entityTypeColor(entity.data.type);
                return (
                  <span
                    className={cn(
                      "inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1",
                      color.bg,
                      color.text,
                      color.ring,
                    )}
                  >
                    {entity.data.type}
                  </span>
                );
              })()}
              <span className="font-mono text-sm font-medium text-gray-900">
                {entity.data.value}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <div>
                <dt className="text-gray-500">Confidence</dt>
                <dd
                  className={cn(
                    "font-medium tabular-nums",
                    confidenceBadgeClass(entity.data.confidence),
                  )}
                >
                  {formatPercent(entity.data.confidence, 1)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Sources</dt>
                <dd className="font-medium tabular-nums text-gray-900">
                  {entity.data.source_count}
                </dd>
              </div>
              {entity.data.first_seen && (
                <div>
                  <dt className="text-gray-500">First seen</dt>
                  <dd className="text-gray-900">
                    {formatDateTime(entity.data.first_seen)}
                  </dd>
                </div>
              )}
              {entity.data.last_seen && (
                <div>
                  <dt className="text-gray-500">Last seen</dt>
                  <dd className="text-gray-900">
                    {formatDateTime(entity.data.last_seen)}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          <nav className="flex shrink-0 border-b border-gray-200 bg-gray-50 text-xs">
            {(["overview", "evidence", "relationships"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "border-b-2 px-3 py-2 font-medium uppercase tracking-wide transition-colors",
                  tab === t
                    ? "border-blue-500 text-blue-700"
                    : "border-transparent text-gray-500 hover:text-gray-700",
                )}
              >
                {t}
                {t === "evidence" && evidence.data && (
                  <span className="ml-1 text-gray-400">
                    {evidence.data.length}
                  </span>
                )}
                {t === "relationships" && relationships.data && (
                  <span className="ml-1 text-gray-400">
                    {relationships.data.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="min-h-0 flex-1 overflow-auto p-4">
            {tab === "overview" && (
              <OverviewTab
                properties={entity.data.properties}
                entityId={selectedEntityId}
              />
            )}
            {tab === "evidence" && (
              <EvidenceTab
                evidence={evidence}
                evidenceOpen={evidenceOpen}
                setEvidenceOpen={setEvidenceOpen}
              />
            )}
            {tab === "relationships" && (
              <RelationshipsTab
                relationships={relationships}
                graph={graph}
                onSelectEntity={selectEntity}
              />
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function OverviewTab({
  properties,
  entityId,
}: {
  properties: Record<string, unknown>;
  entityId: string;
}) {
  const entries = Object.entries(properties ?? {});
  if (entries.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No additional properties recorded for this entity.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
        Properties
      </div>
      <dl className="space-y-1 rounded-md border border-gray-200 bg-gray-50 p-3 text-xs">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="shrink-0 font-medium text-gray-600">{k}</dt>
            <dd className="break-all font-mono text-gray-900">
              {typeof v === "string" ? v : JSON.stringify(v)}
            </dd>
          </div>
        ))}
      </dl>
      <div className="pt-2 text-[10px] text-gray-400">id: {entityId}</div>
    </div>
  );
}

function EvidenceTab({
  evidence,
  evidenceOpen,
  setEvidenceOpen,
}: {
  evidence: ReturnType<typeof useEntityEvidence>;
  evidenceOpen: Record<string, boolean>;
  setEvidenceOpen: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
}) {
  if (evidence.isLoading) return <LoadingState rows={3} />;
  if (evidence.error)
    return <ErrorState message="Failed to load evidence." />;
  if (!evidence.data || evidence.data.length === 0) {
    return (
      <EmptyState
        title="No evidence yet"
        description="Observations tied to this entity will appear here."
      />
    );
  }
  return (
    <ul className="space-y-2">
      {evidence.data.map((obs) => {
        const id = obs.id;
        const open = evidenceOpen[id] ?? false;
        return (
          <li
            key={id}
            className="rounded-md border border-gray-200 bg-white"
          >
            <button
              onClick={() =>
                setEvidenceOpen((s) => ({ ...s, [id]: !open }))
              }
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-gray-50"
            >
              <span className="flex items-center gap-2">
                <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
                  {obs.source_adapter}
                </span>
                <span className="font-mono text-xs text-gray-900">
                  {obs.target}
                </span>
              </span>
              {open ? (
                <ChevronRight className="h-3.5 w-3.5 rotate-90 text-gray-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
              )}
            </button>
            {open && (
              <div className="border-t border-gray-100 bg-gray-50 px-3 py-2">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                  <div>
                    <span className="text-gray-500">Collected:</span>{" "}
                    <span className="font-mono text-gray-900">
                      {formatDateTime(obs.collected_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Confidence:</span>{" "}
                    <span className="font-mono text-gray-900">
                      {formatPercent(obs.confidence, 0)}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-500">Method:</span>{" "}
                    <span className="font-mono text-gray-900">
                      {obs.method || "—"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-500">Normalized:</span>{" "}
                    <span className="font-mono text-gray-900">
                      {obs.normalized_value || "—"}
                    </span>
                  </div>
                </div>
                <details className="mt-2">
                  <summary className="cursor-pointer text-[11px] font-medium text-blue-600 hover:text-blue-800">
                    Raw response
                  </summary>
                  <pre className="mt-1 max-h-64 overflow-auto rounded bg-gray-900 px-2 py-1.5 text-[10px] text-gray-100">
                    {JSON.stringify(obs.raw_response, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function RelationshipsTab({
  relationships,
  graph,
  onSelectEntity,
}: {
  relationships: ReturnType<typeof useEntityRelationships>;
  graph: ReturnType<typeof useInvestigationGraph>["data"];
  onSelectEntity: (id: string) => void;
}) {
  if (relationships.isLoading) return <LoadingState rows={3} />;
  if (relationships.error)
    return <ErrorState message="Failed to load relationships." />;
  if (!relationships.data || relationships.data.length === 0) {
    return (
      <EmptyState
        title="No relationships"
        description="This entity has no connections in the graph yet."
      />
    );
  }

  const labelById: Record<string, string> = {};
  if (graph) {
    for (const n of graph.nodes) {
      labelById[n.data.id] = n.data.label || n.data.id;
    }
  }

  return (
    <ul className="space-y-1.5">
      {relationships.data.map((rel) => {
        const otherId =
          rel.source_entity_id === relationships.data![0]?.source_entity_id
            ? rel.target_entity_id
            : rel.source_entity_id;
        const otherLabel = labelById[otherId] ?? otherId;
        return (
          <li
            key={rel.id}
            className="rounded-md border border-gray-200 bg-white px-3 py-2 text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-700">
                {rel.type.replace(/_/g, " ")}
              </span>
              <span
                className={cn(
                  "tabular-nums",
                  confidenceBadgeClass(rel.confidence),
                )}
              >
                {formatPercent(rel.confidence, 0)}
              </span>
            </div>
            <button
              onClick={() => onSelectEntity(otherId)}
              className="mt-1 flex w-full items-center gap-1.5 truncate text-left font-mono text-xs text-blue-600 hover:text-blue-800"
            >
              <Link2 className="h-3 w-3 shrink-0" />
              <span className="truncate">{otherLabel}</span>
            </button>
            {rel.method && (
              <div className="mt-1 text-[10px] text-gray-500">
                via {rel.method}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
