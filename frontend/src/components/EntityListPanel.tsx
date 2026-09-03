import { useMemo, useState } from "react";
import { ChevronRight, Filter, X } from "lucide-react";
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
      actions={
        <div className="flex items-center gap-1">
          <span className="text-xs text-gray-500">
            {filteredRows.length}/{rows.length}
          </span>
          <button
            onClick={() => setFilterOpen(!filterOpen)}
            className={cn(
              "rounded p-1 hover:bg-gray-100",
              filterOpen && "bg-gray-100",
            )}
            aria-label="Toggle filters"
          >
            <Filter className="h-4 w-4 text-gray-600" />
          </button>
        </div>
      }
      bodyClassName="p-0"
    >
      {filterOpen && (
        <div className="space-y-3 border-b border-gray-200 bg-gray-50 px-4 py-3">
          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-gray-600">
              Search
            </label>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by value or type..."
                className="block w-full rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  className="rounded p-1 text-gray-400 hover:bg-gray-200"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-gray-600">
              Type
            </label>
            <div className="mt-1 flex flex-wrap gap-1">
              {TYPE_OPTIONS.map((t) => {
                const color = entityTypeColor(t);
                const active = typeFilter.has(t);
                return (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 transition-opacity",
                      color.bg,
                      color.text,
                      color.ring,
                      active ? "opacity-100" : "opacity-40 hover:opacity-70",
                    )}
                  >
                    {t}
                  </button>
                );
              })}
              {typeFilter.size > 0 && (
                <button
                  onClick={clearTypeFilter}
                  className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-gray-700 hover:bg-gray-300"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-gray-600">
              Min Confidence: {formatPercent(minConfidence, 0)}
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              className="mt-1 w-full"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-wide text-gray-600">
              Sort
            </label>
            <select
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as typeof sortBy)
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
              className="text-xs font-medium text-blue-600 hover:text-blue-800"
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
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="sticky top-0 z-10 bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                  Value
                </th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                  Conf.
                </th>
                <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                  Src
                </th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredRows.map((row) => {
                const isSelected = row.id === selectedEntityId;
                const color = entityTypeColor(row.type);
                return (
                  <tr
                    key={row.id}
                    onClick={() => selectEntity(row.id)}
                    className={cn(
                      "cursor-pointer hover:bg-gray-50",
                      isSelected && "bg-blue-50 hover:bg-blue-50",
                    )}
                  >
                    <td className="whitespace-nowrap px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1",
                          color.bg,
                          color.text,
                          color.ring,
                        )}
                      >
                        {row.type}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="block max-w-[200px] truncate font-mono text-sm text-gray-900">
                        {row.value}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <span
                        className={cn(
                          "text-sm tabular-nums",
                          confidenceBadgeClass(row.confidence),
                        )}
                      >
                        {formatPercent(row.confidence, 0)}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <span className="text-sm tabular-nums text-gray-600">
                        {row.source_count}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
