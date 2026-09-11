import { useMemo, useState, useRef } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";
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

  const [isMinimized, setIsMinimized] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return; // Only left click
    setIsDragging(true);
    dragStart.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

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
    <div 
      className={cn(
        "absolute right-4 top-4 z-10 w-48 rounded-lg border border-[var(--nx-border)] bg-[var(--nx-surface-1)] overflow-hidden flex flex-col transition-shadow",
        isDragging ? "shadow-lg shadow-black/20" : "shadow-sm"
      )}
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        cursor: isDragging ? 'grabbing' : 'auto'
      }}
    >
      <div className="px-3.5 py-2.5 flex items-center justify-between select-none">
        <div 
          className="flex items-center cursor-grab active:cursor-grabbing text-[var(--nx-text-muted)] hover:text-[var(--nx-text-primary)] transition-colors flex-1"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          <h3 className="text-[10px] font-semibold tracking-wider text-[var(--nx-text-primary)] whitespace-nowrap">
            KNOWLEDGE GRAPH
          </h3>
        </div>
        
        <div className="flex items-center gap-2 pl-2">
          {graphTypeFilter.size > 0 && !isMinimized && (
            <button
              onClick={() => clearGraphTypeFilter()}
              className="text-[10px] font-medium text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors whitespace-nowrap"
            >
              Reset
            </button>
          )}
          <button 
            onClick={() => setIsMinimized(!isMinimized)}
            className="text-[var(--nx-text-muted)] hover:text-[var(--nx-text-primary)] transition-colors"
          >
            {isMinimized ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
      
      {!isMinimized && (
        <div className="flex flex-col py-1.5 border-t border-[var(--nx-border)]">
          {presentTypes.map(({ type, count }) => {
            const color = NODE_TYPE_COLORS[type] ?? DEFAULT_NODE_COLOR;
            const active =
              graphTypeFilter.size === 0 || graphTypeFilter.has(type);
            return (
              <button
                key={type}
                onClick={() => toggleGraphType(type)}
                className={cn(
                  "flex items-center justify-between px-3.5 py-1.5 transition-colors hover:bg-[var(--nx-surface-2)]",
                  active ? "opacity-100" : "opacity-40",
                )}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-xs font-medium text-[var(--nx-text-secondary)] truncate">{type}</span>
                </div>
                <span className="text-xs font-semibold text-[var(--nx-text-muted)]">{count}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
