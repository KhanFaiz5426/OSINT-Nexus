import {
  Activity,
  Brain,
  Network,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { useInvestigationGraph, useInvestigationStatus } from "../hooks/useApi";
import { cn } from "../lib/utils";

const TERMINAL_STATES = new Set(["completed", "stopped", "error"]);

export function WorkstationStatusBar() {
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const openTabs = useWorkspaceStore((s) => s.openTabs);
  const activeTab = openTabs.find((t) => t.id === activeTabId);

  const bottomDrawerOpen = useWorkspaceStore((s) => s.bottomDrawerOpen);
  const toggleBottomDrawer = useWorkspaceStore((s) => s.toggleBottomDrawer);
  const bottomTab = useWorkspaceStore((s) => s.bottomTab);
  const setBottomTab = useWorkspaceStore((s) => s.setBottomTab);
  const graphLayout = useWorkspaceStore((s) => s.graphLayout);

  const { data: statusData } = useInvestigationStatus(activeTabId ?? "", {
    refetchInterval: activeTabId ? 3_000 : undefined,
  });

  const isTerminal = statusData ? TERMINAL_STATES.has(statusData.status) : false;

  // Stop graph polling when investigation reaches terminal state
  const { data: graphData } = useInvestigationGraph(activeTabId ?? "", {
    refetchInterval: activeTabId && !isTerminal ? 5_000 : undefined,
  });

  const nodeCount = graphData?.nodes.length ?? 0;
  const edgeCount = graphData?.edges.length ?? 0;
  const isRunning = statusData?.status === "running";

  return (
    <footer className="flex h-6 shrink-0 items-center justify-between border-t border-[var(--nx-border)] bg-[var(--nx-base)] px-3 text-[11px] select-none text-[var(--nx-text-tertiary)] font-mono">
      {/* Left: Active investigation info */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              isRunning
                ? "bg-amber-400 animate-ping"
                : activeTabId
                  ? "bg-emerald-400"
                  : "bg-[var(--nx-text-muted)]",
            )}
          />
          <span className="text-[var(--nx-text-secondary)]">
            {isRunning
              ? "Running Collection..."
              : activeTabId
                ? `Active: ${activeTab?.target}`
                : "Workstation Ready"}
          </span>
        </div>

        {statusData && (
          <div className="hidden items-center gap-2 md:flex border-l border-[var(--nx-border)] pl-3">
            <span>
              API Budget: {statusData.api_calls_used}/{statusData.api_budget}
            </span>
          </div>
        )}
      </div>

      {/* Center: Graph metrics */}
      <div className="flex items-center gap-2">
        {activeTabId ? (
          <span className="flex items-center gap-1 text-[var(--nx-text-secondary)]">
            <Network className="h-3 w-3 text-[var(--nx-accent)]" />
            <span>
              {nodeCount} nodes · {edgeCount} edges
            </span>
            <span className="text-[var(--nx-text-muted)]">({graphLayout})</span>
          </span>
        ) : (
          <span className="text-[var(--nx-text-muted)]">No active graph</span>
        )}
      </div>

      {/* Right: Drawer Tab Buttons */}
      <div className="flex items-center gap-1">
        {activeTabId && (
          <>
            <button
              onClick={() => {
                if (bottomDrawerOpen && bottomTab === "timeline") {
                  toggleBottomDrawer();
                } else {
                  setBottomTab("timeline");
                }
              }}
              className={cn(
                "flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors",
                bottomDrawerOpen && bottomTab === "timeline"
                  ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)] font-medium"
                  : "hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-secondary)]",
              )}
              title="Toggle Activity Timeline"
            >
              <Activity className="h-3 w-3" />
              <span className="hidden sm:inline">Timeline</span>
            </button>

            <button
              onClick={() => {
                if (bottomDrawerOpen && bottomTab === "entity-intel") {
                  toggleBottomDrawer();
                } else {
                  setBottomTab("entity-intel");
                }
              }}
              className={cn(
                "flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors",
                bottomDrawerOpen && bottomTab === "entity-intel"
                  ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)] font-medium"
                  : "hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-secondary)]",
              )}
              title="Toggle Entity Intelligence"
            >
              <Brain className="h-3 w-3" />
              <span className="hidden sm:inline">Entity Intel</span>
            </button>
          </>
        )}
      </div>
    </footer>
  );
}
