import {
  Brain,
  ShieldCheck,
  AlertTriangle,
  Link2,
  Target,
  Eye,
  ChevronDown,
  ChevronRight,
  Database,
  GitBranch,
  ExternalLink,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Loader2,
  HelpCircle,
  Clock,
  Ban,
} from "lucide-react";
import { useState } from "react";
import { useWorkspaceStore } from "../store/workspace";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import {
  useEntity,
  useEntityEvidence,
  useEntityRelationships,
  useEntityAIAnalysis,
  useInvestigationGraph,
  useSourceAvailability,
} from "../hooks/useApi";
import {
  confidenceBadgeClass,
  entityTypeColor,
  formatPercent,
  formatDateTime,
  entityProfileUrl,
} from "../lib/format";
import type { SourceAvailabilityStatus } from "../api/investigations";
import { cn } from "../lib/utils";

interface EntityIntelligencePanelProps {
  investigationId: string;
}

export function EntityIntelligencePanel({
  investigationId,
}: EntityIntelligencePanelProps) {
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
  const aiAnalysis = useEntityAIAnalysis(
    selectedEntityId ?? undefined,
    investigationId,
  );
  const { data: graph } = useInvestigationGraph(investigationId);
  const sourceAvailability = useSourceAvailability(
    selectedEntityId ?? undefined,
    investigationId,
  );

  if (!selectedEntityId) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          icon={<Brain className="h-10 w-10" />}
          title="Select an entity"
          description="Click any entity in the list or graph node to view intelligence analysis."
        />
      </div>
    );
  }

  if (entity.isLoading) {
    return (
      <div className="p-4">
        <LoadingState label="Loading entity data..." rows={4} />
      </div>
    );
  }

  if (entity.error) {
    return (
      <div className="p-4">
        <ErrorState
          message="Failed to load entity data."
          onRetry={() => entity.refetch()}
        />
      </div>
    );
  }

  if (!entity.data) return null;

  const ent = entity.data;
  const ai = aiAnalysis.data;
  const analysis = ai?.analysis;
  const color = entityTypeColor(ent.type);

  // Build neighbor label map
  const labelById: Record<string, string> = {};
  if (graph) {
    for (const n of graph.nodes) {
      labelById[n.data.id] = n.data.label || n.data.id;
    }
  }

  // Confidence classification
  const confLabel =
    ent.confidence >= 0.8
      ? "High"
      : ent.confidence >= 0.5
        ? "Medium"
        : ent.confidence > 0
          ? "Low"
          : "Unrated";
  const confColor =
    ent.confidence >= 0.8
      ? "text-emerald-400"
      : ent.confidence >= 0.5
        ? "text-amber-400"
        : ent.confidence > 0
          ? "text-orange-400"
          : "text-slate-400";
  const confBannerBorder =
    ent.confidence >= 0.8
      ? "border-emerald-500/30"
      : ent.confidence >= 0.5
        ? "border-amber-500/30"
        : ent.confidence > 0
          ? "border-orange-500/30"
          : "border-slate-500/30";
  const confBannerBg =
    ent.confidence >= 0.8
      ? "bg-emerald-500/5"
      : ent.confidence >= 0.5
        ? "bg-amber-500/5"
        : ent.confidence > 0
          ? "bg-orange-500/5"
          : "bg-slate-500/5";

  // Determine if AI analysis is real vs fallback
  const hasAiAnalysis = !!aiAnalysis.data && !aiAnalysis.error;
  const isFallback =
    hasAiAnalysis &&
    analysis?.significance === "AI analysis not available. Manual review recommended.";

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* ── Entity Header ────────────────────────────────────────────── */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span
                className={cn(
                  "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1",
                  color.bg,
                  color.text,
                  color.ring,
                )}
              >
                {ent.type}
              </span>
              <span className="font-mono text-sm font-semibold text-[var(--nx-text-primary)] truncate">
                {ent.value}
              </span>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-[var(--nx-text-muted)]">
              <span>{ent.source_count} source{ent.source_count !== 1 ? "s" : ""}</span>
              {ent.first_seen && (
                <>
                  <span className="text-[var(--nx-border-strong)]">·</span>
                  <span>First seen {formatDateTime(ent.first_seen)}</span>
                </>
              )}
              {ent.last_seen && ent.last_seen !== ent.first_seen && (
                <>
                  <span className="text-[var(--nx-border-strong)]">·</span>
                  <span>Last seen {formatDateTime(ent.last_seen)}</span>
                </>
              )}
            </div>
          </div>
          {/* Visit Source action with availability status */}
          {(() => {
            const profileUrl = entityProfileUrl(ent.type, ent.value, ent.sources, ent.properties as Record<string, unknown>);
            if (!profileUrl) return null;

            const avail = sourceAvailability.data;
            const statusIcon = avail ? getAvailabilityIcon(avail.status) : null;
            const statusColor = avail ? getAvailabilityColor(avail.status) : "";
            const tooltipText = avail
              ? avail.detail
              : "Source URL from investigation evidence";

            return (
              <div className="shrink-0 flex items-center gap-1.5">
                <a
                  href={profileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2.5 py-1.5 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-accent)] transition-colors"
                  title={tooltipText}
                >
                  <ExternalLink className="h-3 w-3" />
                  Visit Source
                </a>
                {sourceAvailability.isLoading && (
                  <span title="Checking source availability...">
                    <Loader2 className="h-3 w-3 animate-spin text-[var(--nx-text-muted)]" />
                  </span>
                )}
                {avail && statusIcon && (
                  <span
                    className={cn("inline-flex items-center", statusColor)}
                    title={avail.detail}
                  >
                    {statusIcon}
                  </span>
                )}
              </div>
            );
          })()}
        </div>

        {/* ── Assessment Banner ────────────────────────────────────────── */}
        <div
          className={cn(
            "flex items-center justify-between rounded-md border px-3 py-2",
            confBannerBorder,
            confBannerBg,
          )}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className={cn("h-3.5 w-3.5", confColor)} />
            <span className="text-xs text-[var(--nx-text-secondary)]">
              Assessed with{" "}
              <span className={cn("font-semibold", confColor)}>
                {confLabel}
              </span>{" "}
              confidence
            </span>
          </div>
          <span
            className={cn(
              "font-mono text-xs font-semibold tabular-nums",
              confidenceBadgeClass(ent.confidence),
            )}
          >
            {formatPercent(ent.confidence, 0)}
          </span>
        </div>

        {/* ── AI Loading ──────────────────────────────────────────────── */}
        {aiAnalysis.isLoading && (
          <div className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-2">
            <LoadingState label="Generating assessment..." rows={1} />
          </div>
        )}

        {/* ── What Is This Entity ─────────────────────────────────────── */}
        {analysis?.what_is && !isFallback && (
          <div>
            <SectionHeader
              icon={<Eye className="h-3.5 w-3.5 text-sky-400" />}
              title="Assessment"
            />
            <p className="text-sm leading-relaxed text-[var(--nx-text-secondary)] pl-5">
              {analysis.what_is}
            </p>
          </div>
        )}

        {/* ── Key Facts (from confirmed_facts + key_information) ────── */}
        <KeyFactsSection
          confirmedFacts={ai?.confirmed_facts}
          keyInformation={analysis?.key_information}
          isLoading={aiAnalysis.isLoading}
          isFallback={isFallback}
        />

        {/* ── Evidence & Sources ──────────────────────────────────────── */}
        <EvidenceSection
          evidence={evidence.data}
          isLoading={evidence.isLoading}
          evidenceSummary={analysis?.evidence_summary}
          hasAiAnalysis={hasAiAnalysis && !isFallback}
        />

        {/* ── Connection to Target ────────────────────────────────────── */}
        {analysis?.connection_to_target && !isFallback && (
          <ConnectionSection
            connectionText={analysis.connection_to_target}
            relationships={relationships.data}
            selectedEntityId={selectedEntityId}
            investigationTarget={ai?.investigation_target}
            labelById={labelById}
            selectEntity={selectEntity}
          />
        )}

        {/* ── Related Entities ────────────────────────────────────────── */}
        {relationships.data && relationships.data.length > 0 && (
          <RelatedEntitiesSection
            relationships={relationships.data}
            selectedEntityId={selectedEntityId}
            labelById={labelById}
            selectEntity={selectEntity}
          />
        )}

        {/* ── Uncertainties & Analytical Notes ───────────────────────── */}
        <CaveatsSection
          uncertainties={analysis?.uncertainties}
          aiInferences={analysis?.ai_inferences}
          isFallback={isFallback}
        />

        {/* ── AI Error ────────────────────────────────────────────────── */}
        {aiAnalysis.error && (
          <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-400">
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
            <span>AI assessment unavailable. Showing evidence-based data only.</span>
          </div>
        )}

        {/* ── Footer ──────────────────────────────────────────────────── */}
        <div className="border-t border-[var(--nx-border)] pt-3 flex items-center justify-between text-[10px] font-mono text-[var(--nx-text-muted)]">
          <span>{selectedEntityId}</span>
          {ai?.generated_at && (
            <span>
              Assessment: {new Date(ai.generated_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-sections ───────────────────────────────────────────────────────── */

function KeyFactsSection({
  confirmedFacts,
  keyInformation,
  isLoading,
  isFallback,
}: {
  confirmedFacts?: Array<{
    fact: string;
    source: string;
    confidence: number;
    collected_at: string;
  }>;
  keyInformation?: string[];
  isLoading: boolean;
  isFallback: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const facts = confirmedFacts ?? [];
  const aiFacts = keyInformation ?? [];
  const hasContent = facts.length > 0 || aiFacts.length > 0;

  if (!hasContent && !isLoading) return null;

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)] hover:text-[var(--nx-text-secondary)] transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Database className="h-3.5 w-3.5 text-emerald-400" />
        Key Facts
        {!isLoading && (
          <span className="font-normal text-[var(--nx-text-muted)]">
            ({facts.length} confirmed, {aiFacts.length} assessed)
          </span>
        )}
      </button>
      {expanded && (
        <div className="space-y-1 pl-5">
          {isLoading ? (
            <LoadingState rows={2} />
          ) : facts.length === 0 && aiFacts.length === 0 ? (
            <p className="text-xs text-[var(--nx-text-muted)] italic">
              Insufficient evidence. No confirmed facts or AI-assessed key
              information available for this entity.
            </p>
          ) : (
            <>
              {facts.map((f, i) => (
                <div
                  key={`fact-${i}`}
                  className="flex items-start gap-2 rounded border border-emerald-500/15 bg-emerald-500/5 px-2.5 py-1.5 text-xs"
                >
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                  <div className="flex-1 min-w-0">
                    <span className="text-[var(--nx-text-secondary)]">
                      {f.fact}
                    </span>
                    <div className="mt-0.5 flex items-center gap-2 text-[10px] text-[var(--nx-text-muted)]">
                      <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1 py-0.5 font-semibold uppercase tracking-wider">
                        {f.source}
                      </span>
                      <span
                        className={cn(
                          "font-mono tabular-nums",
                          confidenceBadgeClass(f.confidence),
                        )}
                      >
                        {formatPercent(f.confidence, 0)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              {aiFacts.map((info, i) => (
                <div
                  key={`ai-${i}`}
                  className="flex items-start gap-2 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2.5 py-1.5 text-xs"
                >
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--nx-accent)]" />
                  <span className="text-[var(--nx-text-secondary)]">
                    {info}
                  </span>
                  <span className="ml-auto shrink-0 text-[9px] font-medium uppercase tracking-wider text-[var(--nx-text-muted)]">
                    Assessed
                  </span>
                </div>
              ))}
              {isFallback && (
                <p className="text-[10px] text-[var(--nx-text-muted)] italic">
                  Note: AI analysis was not performed. Items marked
                  &ldquo;Assessed&rdquo; are deterministic observations, not LLM
                  inferences.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceSection({
  evidence,
  isLoading,
  evidenceSummary,
  hasAiAnalysis,
}: {
  evidence?: Array<{
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
  }>;
  isLoading: boolean;
  evidenceSummary?: string;
  hasAiAnalysis: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const items = evidence ?? [];

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)] hover:text-[var(--nx-text-secondary)] transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Database className="h-3.5 w-3.5 text-emerald-400" />
        Evidence & Sources
        {!isLoading && (
          <span className="font-normal text-[var(--nx-text-muted)]">
            ({items.length} observation{items.length !== 1 ? "s" : ""})
          </span>
        )}
      </button>
      {expanded && (
        <div className="space-y-1.5 pl-5">
          {isLoading ? (
            <LoadingState rows={2} />
          ) : items.length === 0 ? (
            <p className="text-xs text-[var(--nx-text-muted)] italic">
              No direct evidence observations recorded for this entity.
            </p>
          ) : (
            <>
              {items.map((obs) => (
                <EvidenceRow key={obs.id} obs={obs} />
              ))}
              {hasAiAnalysis && evidenceSummary && (
                <p className="mt-1 text-[11px] leading-relaxed text-[var(--nx-text-muted)] italic border-t border-[var(--nx-border-subtle)] pt-1.5">
                  {evidenceSummary}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceRow({
  obs,
}: {
  obs: {
    id: string;
    source_adapter: string;
    method: string;
    target: string;
    confidence: number;
    status: string;
    collected_at: string;
    raw_response: Record<string, unknown>;
  };
}) {
  const [showRaw, setShowRaw] = useState(false);
  const hasRaw = obs.raw_response && Object.keys(obs.raw_response).length > 0;

  return (
    <div className="rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] text-xs">
      <div className="flex items-center gap-2 px-2.5 py-1.5">
        <span className="inline-flex items-center rounded bg-[var(--nx-surface-4)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
          {obs.source_adapter}
        </span>
        <span className="font-mono text-[var(--nx-text-secondary)] truncate flex-1">
          {obs.method} → {obs.target}
        </span>
        <span
          className={cn(
            "font-mono tabular-nums text-[10px]",
            confidenceBadgeClass(obs.confidence),
          )}
        >
          {formatPercent(obs.confidence, 0)}
        </span>
        {hasRaw && (
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)] transition-colors"
          >
            {showRaw ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
      </div>
      {showRaw && hasRaw && (
        <div className="border-t border-[var(--nx-border-subtle)] px-2.5 py-2">
          <pre className="max-h-40 overflow-auto font-mono text-[10px] text-[var(--nx-text-muted)] whitespace-pre-wrap break-all">
            {JSON.stringify(obs.raw_response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function ConnectionSection({
  connectionText,
  relationships,
  selectedEntityId,
  investigationTarget,
  labelById,
  selectEntity,
}: {
  connectionText: string;
  relationships?: Array<{
    id: string;
    source_entity_id: string;
    target_entity_id: string;
    type: string;
    confidence: number;
  }>;
  selectedEntityId: string;
  investigationTarget?: string;
  labelById: Record<string, string>;
  selectEntity: (id: string) => void;
}) {
  // Find relationship paths that connect to the investigation target
  const targetRels =
    relationships?.filter(
      (r) =>
        r.source_entity_id === selectedEntityId ||
        r.target_entity_id === selectedEntityId,
    ) ?? [];

  return (
    <div>
      <SectionHeader
        icon={<Target className="h-3.5 w-3.5 text-purple-400" />}
        title="Connection to Investigation Target"
      />
      <div className="pl-5 space-y-2">
        <p className="text-sm text-[var(--nx-text-secondary)]">
          {connectionText}
        </p>
        {targetRels.length > 0 && investigationTarget && (
          <div className="flex flex-wrap gap-1.5">
            {targetRels.slice(0, 5).map((rel) => {
              const otherId =
                rel.source_entity_id === selectedEntityId
                  ? rel.target_entity_id
                  : rel.source_entity_id;
              const otherLabel = labelById[otherId] ?? otherId;
              return (
                <button
                  key={rel.id}
                  onClick={() => selectEntity(otherId)}
                  className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-1.5 py-0.5 text-[10px] text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-accent)] transition-colors"
                >
                  <GitBranch className="h-2.5 w-2.5 text-[var(--nx-text-muted)]" />
                  <span className="font-mono truncate max-w-[100px]">
                    {otherLabel}
                  </span>
                  <span className="text-[var(--nx-text-muted)]">
                    {rel.type.replace(/_/g, " ")}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function RelatedEntitiesSection({
  relationships,
  selectedEntityId,
  labelById,
  selectEntity,
}: {
  relationships: Array<{
    id: string;
    source_entity_id: string;
    target_entity_id: string;
    type: string;
    confidence: number;
  }>;
  selectedEntityId: string;
  labelById: Record<string, string>;
  selectEntity: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visibleCount = 6;
  const showExpand = relationships.length > visibleCount;
  const visible = expanded
    ? relationships
    : relationships.slice(0, visibleCount);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)] hover:text-[var(--nx-text-secondary)] transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <Link2 className="h-3.5 w-3.5 text-sky-400" />
        Related Entities
        <span className="font-normal text-[var(--nx-text-muted)]">
          ({relationships.length})
        </span>
      </button>
      {expanded && (
        <div className="flex flex-wrap gap-1.5 pl-5">
          {visible.map((rel) => {
            const otherId =
              rel.source_entity_id === selectedEntityId
                ? rel.target_entity_id
                : rel.source_entity_id;
            const otherLabel = labelById[otherId] ?? otherId;
            const otherType = otherId.split(":")[0] ?? "";
            const otherColor = entityTypeColor(otherType);
            return (
              <button
                key={rel.id}
                onClick={() => selectEntity(otherId)}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-accent)] transition-colors"
              >
                <span
                  className={cn(
                    "inline-flex items-center rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider ring-1",
                    otherColor.bg,
                    otherColor.text,
                    otherColor.ring,
                  )}
                >
                  {otherType}
                </span>
                <span className="font-mono truncate max-w-[120px]">
                  {otherLabel}
                </span>
                <span className="text-[10px] text-[var(--nx-text-muted)]">
                  {rel.type.replace(/_/g, " ")}
                </span>
              </button>
            );
          })}
          {showExpand && !expanded && (
            <span className="text-[10px] text-[var(--nx-text-muted)] self-center">
              +{relationships.length - visibleCount} more
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function CaveatsSection({
  uncertainties,
  aiInferences,
  isFallback,
}: {
  uncertainties?: string[];
  aiInferences?: string[];
  isFallback: boolean;
}) {
  const uItems = uncertainties ?? [];
  const aItems = aiInferences ?? [];
  const hasContent = uItems.length > 0 || aItems.length > 0;

  if (!hasContent) return null;

  return (
    <div>
      <SectionHeader
        icon={<AlertTriangle className="h-3.5 w-3.5 text-amber-400" />}
        title="Uncertainties & Caveats"
      />
      <div className="space-y-1 pl-5">
        {uItems.map((u, i) => (
          <div
            key={`u-${i}`}
            className="flex items-start gap-2 rounded border border-amber-500/15 bg-amber-500/5 px-2.5 py-1.5 text-xs text-amber-300/90"
          >
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 opacity-70" />
            <span>{u}</span>
          </div>
        ))}
        {aItems.map((inf, i) => (
          <div
            key={`i-${i}`}
            className="flex items-start gap-2 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2.5 py-1.5 text-xs text-[var(--nx-text-muted)]"
          >
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--nx-accent)] opacity-60" />
            <span>{inf}</span>
            <span className="ml-auto shrink-0 text-[9px] font-medium uppercase tracking-wider text-[var(--nx-text-muted)]">
              Analytical note
            </span>
          </div>
        ))}
        {isFallback && (
          <p className="text-[10px] text-[var(--nx-text-muted)] italic">
            AI analysis was not performed. These are deterministic observations
            only.
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Source Availability Helpers ──────────────────────────────────────────── */

function getAvailabilityIcon(status: SourceAvailabilityStatus) {
  switch (status) {
    case "available":
      return <CheckCircle2 className="h-3 w-3" />;
    case "not_found":
      return <XCircle className="h-3 w-3" />;
    case "redirected":
      return <ExternalLink className="h-3 w-3" />;
    case "access_denied":
    case "auth_required":
      return <ShieldAlert className="h-3 w-3" />;
    case "rate_limited":
      return <Clock className="h-3 w-3" />;
    case "temporarily_unavailable":
      return <AlertTriangle className="h-3 w-3" />;
    case "blocked":
      return <Ban className="h-3 w-3" />;
    case "unknown":
    default:
      return <HelpCircle className="h-3 w-3" />;
  }
}

function getAvailabilityColor(status: SourceAvailabilityStatus): string {
  switch (status) {
    case "available":
      return "text-emerald-400";
    case "not_found":
      return "text-slate-400";
    case "redirected":
      return "text-sky-400";
    case "access_denied":
    case "auth_required":
      return "text-amber-400";
    case "rate_limited":
      return "text-orange-400";
    case "temporarily_unavailable":
      return "text-orange-400";
    case "blocked":
      return "text-red-400";
    case "unknown":
    default:
      return "text-slate-400";
  }
}

/* ─── Utility sub-components ─────────────────────────────────────────────── */

function SectionHeader({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <h3 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
      {icon}
      {title}
    </h3>
  );
}
