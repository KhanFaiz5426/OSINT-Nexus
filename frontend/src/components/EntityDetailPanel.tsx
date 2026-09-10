import { useState } from "react";
import { ChevronRight, Link2, X, ExternalLink, Globe, User } from "lucide-react";
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

  return (
    <Panel
      className="h-full border-0 rounded-none bg-transparent"
      bodyClassName="p-0 flex flex-col flex-1 min-h-0"
      title={
        selectedEntityId ? (
          <span className="flex items-center gap-2">
            <span>Inspector</span>
            <span className="font-mono text-[10px] normal-case text-[var(--nx-text-muted)]">
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
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
            aria-label="Close entity panel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )
      }
    >
      {!selectedEntityId && (
        <EmptyState
          title="No entity selected"
          description="Click any entity in the list or any node in the graph to inspect details."
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
          {/* Entity header */}
          <div className="border-b border-[var(--nx-border)] px-4 py-3">
            <div className="flex items-center gap-2">
              {(() => {
                const color = entityTypeColor(entity.data.type);
                return (
                  <span
                    className={cn(
                      "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1",
                      color.bg,
                      color.text,
                      color.ring,
                    )}
                  >
                    {entity.data.type}
                  </span>
                );
              })()}
              <span className="font-mono text-sm font-medium text-[var(--nx-text-primary)]">
                {entity.data.value}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <div>
                <dt className="text-[var(--nx-text-muted)]">Confidence</dt>
                <dd
                  className={cn(
                    "font-medium font-mono tabular-nums",
                    confidenceBadgeClass(entity.data.confidence),
                  )}
                >
                  {formatPercent(entity.data.confidence, 1)}
                </dd>
              </div>
              <div>
                <dt className="text-[var(--nx-text-muted)]">Sources</dt>
                <dd className="font-medium font-mono tabular-nums text-[var(--nx-text-secondary)]">
                  {entity.data.source_count}
                </dd>
              </div>
              {entity.data.first_seen && (
                <div>
                  <dt className="text-[var(--nx-text-muted)]">First seen</dt>
                  <dd className="text-[var(--nx-text-secondary)]">
                    {formatDateTime(entity.data.first_seen)}
                  </dd>
                </div>
              )}
              {entity.data.last_seen && (
                <div>
                  <dt className="text-[var(--nx-text-muted)]">Last seen</dt>
                  <dd className="text-[var(--nx-text-secondary)]">
                    {formatDateTime(entity.data.last_seen)}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Tabs */}
          <nav className="flex shrink-0 border-b border-[var(--nx-border)] text-xs">
            {(["overview", "evidence", "relationships"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "border-b-2 px-3 py-2 font-medium uppercase tracking-wider transition-colors",
                  tab === t
                    ? "border-[var(--nx-accent)] text-[var(--nx-accent)]"
                    : "border-transparent text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
              >
                {t}
                {t === "evidence" && evidence.data && (
                  <span className="ml-1 text-[var(--nx-text-muted)]">
                    {evidence.data.length}
                  </span>
                )}
                {t === "relationships" && relationships.data && (
                  <span className="ml-1 text-[var(--nx-text-muted)]">
                    {relationships.data.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          {/* Tab content */}
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {tab === "overview" && (
              <OverviewTab
                properties={entity.data.properties}
                sources={entity.data.sources ?? (entity.data.properties?.sources as string[] | undefined)}
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
  sources,
  entityId,
}: {
  properties: Record<string, unknown>;
  sources: string[] | undefined;
  entityId: string;
}) {
  const allEntries = Object.entries(properties ?? {});
  const otherEntries = allEntries.filter(([k]) => !["sources", "_sources", "_evidence_ids"].includes(k));

  return (
    <div className="space-y-3">
      {/* Sources section */}
      {(sources && sources.length > 0) && (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
            Sources
          </div>
          <ul className="space-y-1">
            {sources.map((source, idx) => (
              <li key={idx} className="flex items-center gap-2 text-xs">
                <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
                  {source}
                </span>
                <span className="text-[var(--nx-text-secondary)]">{sourceLabel(source)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Profile URLs / External Links section */}
      {(() => {
        const profileUrl = properties?.profile_url as string | undefined;
        const url = properties?.url as string | undefined;
        const domain = properties?.domain as string | undefined;
        const links: { label: string; url: string; icon: React.ElementType }[] = [];

        if (profileUrl && isValidUrl(profileUrl)) {
          links.push({ label: "Profile", url: profileUrl, icon: User });
        }
        if (url && isValidUrl(url) && url !== profileUrl) {
          links.push({ label: "URL", url, icon: Globe });
        }
        if (domain && isValidUrl(`https://${domain}`)) {
          links.push({ label: "Domain", url: `https://${domain}`, icon: Globe });
        }

        if (links.length > 0) {
          return (
            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                External Links
              </div>
              <div className="flex flex-wrap gap-2">
                {links.map((link, idx) => (
                  <a
                    key={idx}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] transition-colors"
                  >
                    <link.icon className="h-3 w-3" />
                    <span>{link.label}</span>
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                ))}
              </div>
            </div>
          );
        }
        return null;
      })()}

      {/* All properties section */}
      {otherEntries.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
            All Properties
          </div>
          <dl className="space-y-1 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] p-3 text-xs max-h-96 overflow-auto">
            {otherEntries.map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="shrink-0 font-medium text-[var(--nx-text-tertiary)]">{k}</dt>
                <dd className="break-all font-mono text-[var(--nx-text-secondary)]">
                  {typeof v === "string" ? v : JSON.stringify(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {otherEntries.length === 0 && !sources?.length && (
        <p className="text-sm text-[var(--nx-text-muted)]">
          No additional properties recorded for this entity.
        </p>
      )}

      <div className="pt-2 text-[10px] font-mono text-[var(--nx-text-muted)]">
        id: {entityId}
      </div>
    </div>
  );
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    search: "Web Search (SearXNG)",
    github: "GitHub",
    gitlab: "GitLab",
    reddit: "Reddit",
    keybase: "Keybase",
    hackernews: "Hacker News",
    dns: "DNS",
    whois: "WHOIS",
    certificate_transparency: "Certificate Transparency",
    http: "HTTP",
    ip_to_asn: "IP-to-ASN",
    threat_intel: "Threat Intel",
    username_probe: "Username Probe",
  };
  return labels[source] ?? source;
}

function isValidUrl(str: string): boolean {
  try {
    new URL(str);
    return true;
  } catch {
    return false;
  }
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
            className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)]"
          >
            <button
              onClick={() =>
                setEvidenceOpen((s) => ({ ...s, [id]: !open }))
              }
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-[var(--nx-surface-4)] transition-colors rounded-md"
            >
              <span className="flex items-center gap-2">
                <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
                  {obs.source_adapter}
                </span>
                <span className="font-mono text-xs text-[var(--nx-text-secondary)]">
                  {obs.target}
                </span>
              </span>
              {open ? (
                <ChevronRight className="h-3.5 w-3.5 rotate-90 text-[var(--nx-text-muted)]" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-[var(--nx-text-muted)]" />
              )}
            </button>
            {open && (
              <div className="border-t border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
                  <div>
                    <span className="text-[var(--nx-text-muted)]">Collected:</span>{" "}
                    <span className="font-mono text-[var(--nx-text-secondary)]">
                      {formatDateTime(obs.collected_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--nx-text-muted)]">Confidence:</span>{" "}
                    <span className="font-mono text-[var(--nx-text-secondary)]">
                      {formatPercent(obs.confidence, 0)}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[var(--nx-text-muted)]">Method:</span>{" "}
                    <span className="font-mono text-[var(--nx-text-secondary)]">
                      {obs.method || "—"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[var(--nx-text-muted)]">Normalized:</span>{" "}
                    <span className="font-mono text-[var(--nx-text-secondary)]">
                      {obs.normalized_value || "—"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[var(--nx-text-muted)]">Status:</span>{" "}
                    <span className="font-mono text-[var(--nx-text-secondary)]">
                      {obs.status}
                    </span>
                  </div>
                </div>
                <details className="mt-2">
                  <summary className="cursor-pointer text-[11px] font-medium text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80">
                    Raw response
                  </summary>
                  <pre className="mt-1 max-h-64 overflow-auto rounded bg-[var(--nx-base)] px-2 py-1.5 text-[10px] text-[var(--nx-text-tertiary)] font-mono">
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
        const otherType = otherId.split(":")[0] ?? "";
        return (
          <li
            key={rel.id}
            className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-2 text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
                {rel.type.replace(/_/g, " ")}
              </span>
              <span
                className={cn(
                  "tabular-nums font-mono",
                  confidenceBadgeClass(rel.confidence),
                )}
              >
                {formatPercent(rel.confidence, 0)}
              </span>
            </div>
            <button
              onClick={() => onSelectEntity(otherId)}
              className="mt-1.5 flex w-full items-center gap-1.5 truncate text-left font-mono text-xs text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors"
            >
              <Link2 className="h-3 w-3 shrink-0" />
              <span className="truncate">{otherLabel}</span>
              {otherType && (
                <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
                  {otherType}
                </span>
              )}
            </button>
            {rel.method && (
              <div className="mt-1 text-[10px] text-[var(--nx-text-muted)]">
                via {rel.method}
              </div>
            )}
            {rel.evidence && rel.evidence.length > 0 && (
              <div className="mt-1 text-[10px] text-[var(--nx-text-muted)]">
                {rel.evidence.length} observation(s) as evidence
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}