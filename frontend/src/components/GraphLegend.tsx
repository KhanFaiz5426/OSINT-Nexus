import { useMemo } from "react";
import { useInvestigationGraph } from "../hooks/useApi";
import { useWorkspaceStore } from "../store/workspace";
import { cn } from "../lib/utils";
import {
  DEFAULT_NODE_COLOR,
  NODE_TYPE_COLORS,
} from "../lib/format";

interface GraphLegendProps {
  investigationId: string;
}

export function GraphLegend({ investigationId }: GraphLegendProps) {
  const { data } = useInvestigationGraph(investigationId);
  const graphTypeFilter = useWorkspaceStore((s) => s.graphTypeFilter);
  const toggleGraphType = useWorkspaceStore((s) => s.toggleGraphType);
  const clearGraphTypeFilter = useWorkspaceStore(
    (s) => s.clearGraphTypeFilter,
  );

  const presentTypes = useMemo(() => {
    if (!data) return [] as Array<{ type: string; count: number }>;
    const counts: Record<string, number> = {};
    for (const n of data.nodes) {
      counts[n.data.type] = (counts[n.data.type] ?? 0) + 1;
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([type, count]) => ({ type, count }));
  }, [data]);

  if (presentTypes.length === 0) return null;

  return (
    <div className="rounded-md border border-gray-200 bg-white p-2">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">
          Legend
        </h3>
        {graphTypeFilter.size > 0 && (
          <button
            onClick={clearGraphTypeFilter}
            className="text-[10px] font-medium text-blue-600 hover:text-blue-800"
          >
            Show all
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1">
        {presentTypes.map(({ type, count }) => {
          const color = NODE_TYPE_COLORS[type] ?? DEFAULT_NODE_COLOR;
          const active =
            graphTypeFilter.size === 0 || graphTypeFilter.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleGraphType(type)}
              className={cn(
                "flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-opacity",
                active ? "opacity-100" : "opacity-30 hover:opacity-70",
              )}
            >
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: color }}
              />
              {type}
              <span className="ml-0.5 text-gray-400">{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
