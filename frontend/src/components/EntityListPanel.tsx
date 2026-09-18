import { useMemo, useState } from "react";
import { ChevronRight, Filter, X, Search } from "lucide-react";
import { useInvestigationGraph } from "../hooks/useApi";
import { useWorkspaceStore } from "../store/workspace";
import { Panel } from "./Panel";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { cn } from "../lib/utils";
import {
  confidenceBadgeClass,
  entityTypeColor,
  formatPercent,
} from "../lib/format";
import type { EntityType, GraphNode } from "../api/investigations";

interface Row {
  id: string;
  type: string;
  value: string;
  confidence: number;
  source_count: number;
}

const TYPE_OPTIONS: EntityType[] = [
  "Domain",
  "Subdomain",
  "IP",
  "ASN",
  "Certificate",
  "Email",
  "URL",
  "Username",
  "Repository",
  "Technology",
  "Organization",
  "Person",
  "ThreatIndicator",
];

export function EntityListPanel({
  investigationId,
}: {
  investigationId: string;
}) {
  const { data, isLoading, error, refetch } = useInvestigationGraph(
    investigationId,
  );
  const selectedEntityId = useWorkspaceStore((s) => s.selectedEntityId);
  const selectEntity = useWorkspaceStore((s) => s.selectEntity);
  const search = useWorkspaceStore((s) => s.entitySearch);
  const setSearch = useWorkspaceStore((s) => s.setEntitySearch);
  const typeFilter = useWorkspaceStore((s) => s.entityTypeFilter);
  const toggleType = useWorkspaceStore((s) => s.toggleEntityType);
  const clearTypeFilter = useWorkspaceStore((s) => s.clearEntityTypeFilter);
  const minConfidence = useWorkspaceStore((s) => s.minConfidence);
  const setMinConfidence = useWorkspaceStore((s) => s.setMinConfidence);
  const sortBy = useWorkspaceStore((s) => s.sortBy);
  const setSortBy = useWorkspaceStore((s) => s.setSortBy);

  const [filterOpen, setFilterOpen] = useState(false);

  const rows = useMemo<Row[]>(() => {
    if (!data) return [];
    return data.nodes.map((n: GraphNode) => ({
      id: n.data.id,
      type: n.data.type,
      value: n.data.label || n.data.id,
      confidence: n.data.confidence ?? 0,
      source_count: n.data.source_count ?? 0,
    }));
  }, [data]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows
      .filter((r) => {
        if (typeFilter.size > 0 && !typeFilter.has(r.type as EntityType))
          return false;
        if (r.confidence < minConfidence) return false;
        if (
          q &&
          !r.value.toLowerCase().includes(q) &&
          !r.type.toLowerCase().includes(q)
        )
          return false;
        return true;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case "value":
            return a.value.localeCompare(b.value);
          case "type":
            return a.type.localeCompare(b.type);
          case "source_count":
            return b.source_count - a.source_count;
          case "confidence":
          default:
            return b.confidence - a.confidence;
        }
      });
  }, [rows, search, typeFilter, minConfidence, sortBy]);

  const filtersActive =
    typeFilter.size > 0 || minConfidence > 0 || search.length > 0;

  return (
    <Panel
      title="Entities"
      className="h-full border-0 rounded-none bg-transparent"
      bodyClassName="p-0 flex flex-col flex-1 min-h-0"
      actions={
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-[var(--nx-text-muted)] tabular-nums">
            {filteredRows.length}/{rows.length}
          </span>
          <button
            onClick={() => setFilterOpen(!filterOpen)}
            className={cn(
              "rounded p-1 transition-colors flex items-center justify-center",
              filtersActive
                ? "bg-[var(--nx-surface-4)] text-[var(--nx-accent)] ring-1 ring-[var(--nx-accent)]"
                : filterOpen
                  ? "bg-[var(--nx-surface-3)] text-[var(--nx-text-primary)]"
                  : "text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)]",
            )}
            aria-label="Toggle filters"
          >
            <Filter className={cn("h-3.5 w-3.5", filtersActive && "fill-current")} />
          </button>
        </div>
      }
    >
      {/* Search — always visible */}
      <div className="border-b border-[var(--nx-border)] px-3 py-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--nx-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search entities..."
            className="block w-full rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] py-1.5 pl-7 pr-7 text-xs text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent-dim)] focus:outline-none transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Expandable filters */}
      {filterOpen && (
        <div className="space-y-3 border-b border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-3 py-2.5">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                Type
              </label>
              {typeFilter.size > 0 && (
                <button
                  onClick={clearTypeFilter}
                  className="text-[9px] font-medium text-[var(--nx-text-muted)] hover:text-[var(--nx-text-primary)]"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {TYPE_OPTIONS.map((t) => {
                const color = entityTypeColor(t);
                const active = typeFilter.has(t);
                // Extract base color string for a solid dot, e.g., "bg-red-500"
                const dotColor = color.bg.replace("/15", "");
                return (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={cn(
                      "flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide border transition-colors",
                      active
                        ? "bg-[var(--nx-surface-4)] border-[var(--nx-text-primary)] text-[var(--nx-text-primary)]"
                        : "bg-[var(--nx-surface-3)] border-[var(--nx-border)] text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-text-secondary)]",
                    )}
                  >
                    <span className={cn("w-1.5 h-1.5 rounded-full", dotColor)} />
                    {t}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)] mb-1">
              <span>Min Confidence</span>
              <span className="text-[var(--nx-text-primary)] font-mono">{formatPercent(minConfidence, 0)}</span>
            </label>
            <div className="flex items-center h-4 w-full">
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={minConfidence}
                onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                className="w-full h-1 bg-[var(--nx-border)] rounded-full appearance-none cursor-pointer accent-[var(--nx-accent)] focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)] mb-1">
              Sort
            </label>
            <select
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as typeof sortBy)
              }
              className="block w-full rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2 py-1.5 text-xs text-[var(--nx-text-primary)] focus:border-[var(--nx-accent-dim)] focus:outline-none transition-colors"
            >
              <option value="confidence">Confidence (high → low)</option>
              <option value="source_count">Source count</option>
              <option value="value">Value (A → Z)</option>
              <option value="type">Type</option>
            </select>
          </div>

          {filtersActive && (
            <button
              onClick={() => {
                clearTypeFilter();
                setSearch("");
                setMinConfidence(0);
              }}
              className="mt-1 block w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] py-1 text-xs text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-text-primary)] transition-colors"
            >
              Reset all filters
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="p-4">
          <ErrorState
            message="Failed to load entities."
            onRetry={() => refetch()}
          />
        </div>
      )}

      {isLoading && <LoadingState rows={5} />}

      {!isLoading && !error && rows.length === 0 && (
        <EmptyState
          title="No entities yet"
          description="Entities will appear here once collection begins."
        />
      )}

      {!isLoading && !error && rows.length > 0 && filteredRows.length === 0 && (
        <EmptyState
          title="No matches"
          description="No entities match your filters. Try adjusting them."
        />
      )}

      {!isLoading && !error && filteredRows.length > 0 && (
        <div className="overflow-y-auto">
          {filteredRows.map((row) => {
            const isSelected = row.id === selectedEntityId;
            const color = entityTypeColor(row.type);
            return (
              <button
                key={row.id}
                onClick={() => selectEntity(row.id)}
                className={cn(
                  "flex w-full items-center gap-2.5 border-b border-[var(--nx-border-subtle)] px-3 py-2 text-left transition-colors",
                  isSelected
                    ? "bg-[var(--nx-accent-subtle)] border-l-2 border-l-[var(--nx-accent)]"
                    : "hover:bg-[var(--nx-surface-3)]",
                )}
              >
                {/* Type dot */}
                <span
                  className={cn(
                    "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ring-1",
                    color.bg,
                    color.text,
                    color.ring,
                  )}
                >
                  {row.type}
                </span>
                {/* Value */}
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-[var(--nx-text-primary)]">
                  {row.value}
                </span>
                {/* Confidence */}
                <span
                  className={cn(
                    "shrink-0 text-[10px] font-mono tabular-nums",
                    confidenceBadgeClass(row.confidence),
                  )}
                >
                  {formatPercent(row.confidence, 0)}
                </span>
                <ChevronRight className="h-3 w-3 shrink-0 text-[var(--nx-text-muted)]" />
              </button>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
