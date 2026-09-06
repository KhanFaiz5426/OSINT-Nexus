import {
  Crosshair,
  Plus,
  FolderOpen,
  Play,
  Square,
  RefreshCw,
  PanelLeft,
  PanelRight,
  PanelBottom,
  Maximize2,
  Share2,
  FileDown,
  ChevronDown,
  Sun,
  Moon,
} from "lucide-react";
import { useState } from "react";
import { useWorkspaceStore, type GraphLayoutName } from "../store/workspace";
import {
  useInvestigation,
  useInvestigationStatus,
  useStartInvestigation,
  useStopInvestigation,
} from "../hooks/useApi";
import { statusBadgeClass } from "../lib/format";
import { Spinner } from "./LoadingState";
import { cn } from "../lib/utils";

export function WorkstationHeader() {
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);

  const leftPanelOpen = useWorkspaceStore((s) => s.leftPanelOpen);
  const toggleLeftPanel = useWorkspaceStore((s) => s.toggleLeftPanel);

  const rightPanelOpen = useWorkspaceStore((s) => s.rightPanelOpen);
  const toggleRightPanel = useWorkspaceStore((s) => s.toggleRightPanel);

  const theme = useWorkspaceStore((s) => s.theme);
  const toggleTheme = useWorkspaceStore((s) => s.toggleTheme);

  const bottomDrawerOpen = useWorkspaceStore((s) => s.bottomDrawerOpen);
  const toggleBottomDrawer = useWorkspaceStore((s) => s.toggleBottomDrawer);
  const setBottomTab = useWorkspaceStore((s) => s.setBottomTab);

  const graphLayout = useWorkspaceStore((s) => s.graphLayout);
  const setGraphLayout = useWorkspaceStore((s) => s.setGraphLayout);
  const triggerFit = useWorkspaceStore((s) => s.triggerFit);

  const [layoutDropdownOpen, setLayoutDropdownOpen] = useState(false);

  // Active investigation data & controls
  const investigation = useInvestigation(activeTabId ?? "");
  const status = useInvestigationStatus(activeTabId ?? "", {
    refetchInterval: activeTabId ? 3000 : undefined,
  });
  const start = useStartInvestigation();
  const stop = useStopInvestigation();

  const inv = investigation.data;
  const st = status.data;

  const isRunning = st?.status === "running";
  const isStartable = st?.status === "created" || ["completed", "stopped", "error"].includes(st?.status ?? "");
  const isStoppable = st?.status === "running";

  const handleStart = () => {
    if (activeTabId) start.mutate(activeTabId);
  };

  const handleStop = () => {
    if (activeTabId) stop.mutate(activeTabId);
  };

  const layouts: Array<{ id: GraphLayoutName; label: string }> = [
    { id: "cose", label: "Force Directed (Cose)" },
    { id: "concentric", label: "Concentric Rings" },
    { id: "circle", label: "Circular" },
    { id: "grid", label: "Orthogonal Grid" },
  ];

  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-3 select-none">
      {/* Left: Brand & Primary Actions */}
      <div className="flex items-center gap-2">
        {/* Brand */}
        <div className="flex items-center gap-2 pr-2 border-r border-[var(--nx-border)]">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]">
            <Crosshair className="h-4 w-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-primary)]">
            OSINT Nexus
          </span>
        </div>

        {/* Primary: + New Investigation */}
        <button
          onClick={() => setNewModalOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-[var(--nx-accent)] px-2.5 py-1 text-xs font-medium text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 shadow-sm"
          title="New Investigation (Ctrl+N)"
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
          <span>New Investigation</span>
        </button>

        {/* Open existing */}
        <button
          onClick={() => setOpenModalOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2.5 py-1 text-xs font-medium text-[var(--nx-text-secondary)] transition-colors hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)]"
          title="Open Investigation (Ctrl+O)"
        >
          <FolderOpen className="h-3.5 w-3.5" />
          <span>Open...</span>
        </button>

        {/* Investigation Controls when an active workspace is open */}
        {activeTabId && inv && (
          <div className="flex items-center gap-2 pl-2 border-l border-[var(--nx-border)]">
            {/* Target pill */}
            <div className="flex items-center gap-1.5 rounded-md bg-[var(--nx-surface-2)] border border-[var(--nx-border)] px-2 py-0.5 text-xs">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                {inv.target_type}
              </span>
              <span className="font-mono text-[var(--nx-text-primary)]">{inv.target}</span>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded px-1.5 py-0.2 text-[9px] font-semibold uppercase tracking-wider",
                  statusBadgeClass(st?.status ?? inv.status),
                )}
              >
                {isRunning && <Spinner className="h-2 w-2" />}
                {st?.status ?? inv.status}
              </span>
            </div>

            {/* Run / Stop controls */}
            {isStartable && (
              <button
                onClick={handleStart}
                disabled={start.isPending}
                className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-xs font-medium text-emerald-400 hover:bg-emerald-500/25 transition-colors disabled:opacity-50"
                title={st?.status === "completed" ? "Re-run Investigation" : "Start Collection"}
              >
                {start.isPending ? <Spinner className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                <span>{st?.status === "completed" ? "Re-run" : "Run"}</span>
              </button>
            )}

            {isStoppable && (
              <button
                onClick={handleStop}
                disabled={stop.isPending}
                className="inline-flex items-center gap-1 rounded bg-red-500/15 border border-red-500/30 px-2 py-0.5 text-xs font-medium text-red-400 hover:bg-red-500/25 transition-colors disabled:opacity-50"
                title="Stop Investigation"
              >
                {stop.isPending ? <Spinner className="h-3 w-3" /> : <Square className="h-3 w-3" />}
                <span>Stop</span>
              </button>
            )}

            <button
              onClick={() => {
                investigation.refetch();
                status.refetch();
              }}
              className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              title="Refresh status"
            >
              <RefreshCw className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* Right: Graph & Panel View Controls */}
      <div className="flex items-center gap-1.5">
        {activeTabId && (
          <>
            {/* Graph Layout Selector */}
            <div className="relative">
              <button
                onClick={() => setLayoutDropdownOpen(!layoutDropdownOpen)}
                className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
                title="Graph Layout"
              >
                <Share2 className="h-3 w-3 text-[var(--nx-accent)]" />
                <span className="capitalize">{graphLayout}</span>
                <ChevronDown className="h-3 w-3 opacity-60" />
              </button>

              {layoutDropdownOpen && (
                <div
                  className="absolute right-0 top-full z-50 mt-1 w-44 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] py-1 shadow-xl"
                  onClick={() => setLayoutDropdownOpen(false)}
                >
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                    Graph Layout
                  </div>
                  {layouts.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => setGraphLayout(l.id)}
                      className={cn(
                        "flex w-full items-center px-2.5 py-1 text-xs text-left transition-colors",
                        graphLayout === l.id
                          ? "bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)] font-medium"
                          : "text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)]",
                      )}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Zoom to fit */}
            <button
              onClick={triggerFit}
              className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
              title="Fit to Canvas (Space)"
            >
              <Maximize2 className="h-3 w-3" />
              <span>Fit</span>
            </button>

            {/* Reports Trigger */}
            <button
              onClick={() => {
                setBottomTab("reports");
              }}
              className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
              title="Export & Reports"
            >
              <FileDown className="h-3 w-3" />
              <span>Reports</span>
            </button>

            {/* Panel Toggles */}
            <div className="flex items-center gap-0.5 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] p-0.5">
              <button
                onClick={toggleLeftPanel}
                className={cn(
                  "rounded p-1 transition-colors",
                  leftPanelOpen
                    ? "bg-[var(--nx-surface-4)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
                title={leftPanelOpen ? "Hide Entities Panel" : "Show Entities Panel"}
              >
                <PanelLeft className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={toggleBottomDrawer}
                className={cn(
                  "rounded p-1 transition-colors",
                  bottomDrawerOpen
                    ? "bg-[var(--nx-surface-4)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
                title={bottomDrawerOpen ? "Hide Bottom Drawer" : "Show Bottom Drawer"}
              >
                <PanelBottom className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={toggleRightPanel}
                className={cn(
                  "rounded p-1 transition-colors",
                  rightPanelOpen
                    ? "bg-[var(--nx-surface-4)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
                title={rightPanelOpen ? "Hide Contextual Inspector" : "Show Contextual Inspector"}
              >
                <PanelRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="h-4 w-px bg-[var(--nx-border)] mx-1" />
          </>
        )}

        {/* Theme toggle button */}
        <button
          onClick={toggleTheme}
          className="flex h-7 w-7 items-center justify-center rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
        >
          {theme === "dark" ? (
            <Sun className="h-3.5 w-3.5 text-amber-400" />
          ) : (
            <Moon className="h-3.5 w-3.5 text-sky-600" />
          )}
        </button>
      </div>
    </header>
  );
}
