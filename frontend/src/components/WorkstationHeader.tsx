import {
  Plus,
  FolderOpen,
  Play,
  Square,
  RefreshCw,
  PanelLeft,
  PanelBottom,
  Maximize2,
  Share2,
  FileDown,
  ChevronDown,
  Sun,
  Moon,
  Trash2,
  Settings,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useWorkspaceStore, type GraphLayoutName } from "../store/workspace";
import {
  useInvestigation,
  useInvestigationStatus,
  useStartInvestigation,
  useStopInvestigation,
  useDeleteInvestigation,
  useInvestigationSSE,
} from "../hooks/useApi";
import { useWorkspaceStatus } from "../hooks/useWorkspaceApi";
import { useWorkspaceActions } from "../hooks/useWorkspaceActions";
import { statusBadgeClass } from "../lib/format";
import { Spinner } from "./LoadingState";
import { ConfirmDialog } from "./ConfirmDialog";
import { ReportGeneratorModal } from "./ReportGeneratorModal";
import { cn } from "../lib/utils";

/** Extract just the filename from a full path. */
function basename(filepath: string): string {
  const parts = filepath.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || filepath;
}

export function WorkstationHeader() {
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);
  const queryClient = useQueryClient();

  // Workspace file management
  const workspaceStatus = useWorkspaceStatus();
  
  const {
    handleNewInvestigation,
    handleOpenWorkspace,
    isWorkspaceBusy,
  } = useWorkspaceActions();

  const activeFile = workspaceStatus.data?.active_workspace ?? null;
  const activeFileName = activeFile ? basename(activeFile) : null;

  const leftPanelOpen = useWorkspaceStore((s) => s.leftPanelOpen);
  const toggleLeftPanel = useWorkspaceStore((s) => s.toggleLeftPanel);

  const theme = useWorkspaceStore((s) => s.theme);
  const toggleTheme = useWorkspaceStore((s) => s.toggleTheme);

  const bottomDrawerOpen = useWorkspaceStore((s) => s.bottomDrawerOpen);
  const toggleBottomDrawer = useWorkspaceStore((s) => s.toggleBottomDrawer);

  const graphLayout = useWorkspaceStore((s) => s.graphLayout);
  const setGraphLayout = useWorkspaceStore((s) => s.setGraphLayout);
  const triggerFit = useWorkspaceStore((s) => s.triggerFit);

  const [layoutDropdownOpen, setLayoutDropdownOpen] = useState(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [openMenuOpen, setOpenMenuOpen] = useState(false);
  const openMenuRef = useRef<HTMLDivElement>(null);

  // Active investigation data & controls
  const investigation = useInvestigation(activeTabId ?? "");
  const status = useInvestigationStatus(activeTabId ?? "", {
    refetchInterval: activeTabId ? 3000 : undefined,
  });

  // SSE for real-time updates
  useInvestigationSSE(activeTabId ?? undefined);
  const start = useStartInvestigation();
  const stop = useStopInvestigation();
  const deleteInv = useDeleteInvestigation();
  const closeTab = useWorkspaceStore((s) => s.closeTab);
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab);

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isSpinning, setIsSpinning] = useState(false);

  const inv = investigation.data;
  const st = status.data;

  const isRunning = st?.status === "running";
  const isStartable = st?.status === "created" || ["stopped", "error"].includes(st?.status ?? "");
  const isStoppable = st?.status === "running";

  const handleStart = () => {
    if (activeTabId) start.mutate(activeTabId);
  };

  const handleStop = () => {
    if (activeTabId) stop.mutate(activeTabId);
  };

  const handleDelete = () => {
    if (!activeTabId) return;
    deleteInv.mutate(activeTabId, {
      onSuccess: () => {
        setDeleteConfirmOpen(false);
        closeTab(activeTabId);
        setActiveTab(null);
      },
    });
  };

  // Close menus on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (openMenuOpen && openMenuRef.current && !openMenuRef.current.contains(e.target as Node)) {
        setOpenMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [openMenuOpen]);

  const layouts: Array<{ id: GraphLayoutName; label: string }> = [
    { id: "cose", label: "Force Directed (Cose)" },
    { id: "concentric", label: "Concentric Rings" },
    { id: "circle", label: "Circular" },
    { id: "grid", label: "Orthogonal Grid" },
  ];

  return (
    <header className="flex h-10 shrink-0 items-center border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-2 select-none">
      {/* ── Minimal No-Workspace State ── */}
      {!activeFile ? (
        <div className="flex w-full items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded">
              <img src="/osint-nexus-logo.png" alt="Logo" className="h-6 w-6 object-contain" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-primary)]">
              OSINT Nexus
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={toggleTheme}
              className="flex h-7 w-7 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-primary)] transition-colors"
              title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {theme === "dark" ? (
                <Sun className="h-3.5 w-3.5 text-amber-400" />
              ) : (
                <Moon className="h-3.5 w-3.5 text-sky-600" />
              )}
            </button>
            <Link
              to="/settings"
              className="flex h-7 w-7 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-primary)] transition-colors"
              title="Settings"
            >
              <Settings className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      ) : (
        /* ── Workspace Active State ── */
        <div className="flex w-full items-center">
          {/* GROUP 1: APP / WORKSPACE */}
          <div className="flex items-center gap-2 pr-2 border-r border-[var(--nx-border)]">
            <div className="flex items-center gap-1.5">
              <div className="flex h-6 w-6 items-center justify-center rounded" title="OSINT Nexus">
                <img src="/osint-nexus-logo.png" alt="Logo" className="h-6 w-6 object-contain" />
              </div>
              <span className="text-[10px] font-bold tracking-widest uppercase text-[var(--nx-text-secondary)]">
                NX
              </span>
              <span className="text-xs text-[var(--nx-text-muted)] opacity-50 px-0.5">|</span>
              <span className="text-xs font-mono font-medium text-[var(--nx-text-primary)] max-w-[180px] truncate" title={activeFile}>
                {activeFileName}
              </span>
            </div>
            
            <div className="h-4 w-px bg-[var(--nx-border)] mx-1" />

            <button
              onClick={handleNewInvestigation}
              disabled={isWorkspaceBusy}
              className="inline-flex items-center gap-1.5 rounded bg-[var(--nx-accent)] px-2 py-1 text-xs font-medium text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 shadow-sm disabled:opacity-50 disabled:pointer-events-none"
              title="New Investigation (Ctrl+N)"
            >
              <Plus className="h-3 w-3" strokeWidth={2.5} />
              <span>New Investigation</span>
            </button>

            <div className="relative" ref={openMenuRef}>
              <button
                onClick={() => setOpenMenuOpen(!openMenuOpen)}
                disabled={isWorkspaceBusy}
                className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs font-medium text-[var(--nx-text-secondary)] transition-colors hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] disabled:opacity-50 disabled:pointer-events-none"
                title="Open..."
              >
                <span>Open</span>
                <ChevronDown className="h-3 w-3 opacity-60" />
              </button>
              {openMenuOpen && (
                <div
                  className="absolute left-0 top-full z-50 mt-1 w-44 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] py-1 shadow-xl"
                >
                  <button
                    onClick={() => { setOpenModalOpen(true); setOpenMenuOpen(false); }}
                    className="flex w-full items-center gap-2.5 px-3 py-1.5 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                    <span>Open Investigation</span>
                  </button>
                  <button
                    onClick={() => { handleOpenWorkspace(); setOpenMenuOpen(false); }}
                    className="flex w-full items-center gap-2.5 px-3 py-1.5 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
                  >
                    {isWorkspaceBusy ? <Spinner className="h-3.5 w-3.5" /> : <FolderOpen className="h-3.5 w-3.5" />}
                    <span>Open Workspace...</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* GROUP 2 & 3: CURRENT INVESTIGATION & ACTIONS */}
          {activeTabId && inv && (
            <div className="flex items-center gap-2 pl-2 border-r border-[var(--nx-border)] pr-2">
              {/* Target pill */}
              <div className="flex items-center gap-1.5 rounded bg-[var(--nx-surface-2)] border border-[var(--nx-border)] px-1.5 py-0.5 text-xs">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  {inv.target_type}
                </span>
                <span className="font-mono text-[var(--nx-text-primary)] max-w-[120px] truncate" title={inv.target}>{inv.target}</span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wider leading-none",
                    statusBadgeClass(st?.status ?? inv.status),
                  )}
                >
                  {isRunning && <Spinner className="h-2 w-2" />}
                  {st?.status ?? inv.status}
                </span>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-0.5">
                {isStartable && (
                  <button
                    onClick={handleStart}
                    disabled={start.isPending}
                    className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-emerald-500/15 hover:text-emerald-400 transition-colors disabled:opacity-50"
                    title="Start Collection"
                  >
                    {start.isPending ? <Spinner className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                  </button>
                )}

                {isStoppable && (
                  <button
                    onClick={handleStop}
                    disabled={stop.isPending}
                    className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-red-500/15 hover:text-red-400 transition-colors disabled:opacity-50"
                    title="Stop Investigation"
                  >
                    {stop.isPending ? <Spinner className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
                  </button>
                )}

                <button
                  onClick={() => {
                    if (isSpinning) return;
                    setIsSpinning(true);
                    investigation.refetch();
                    status.refetch();
                    queryClient.invalidateQueries({ queryKey: ["graph", activeTabId] });
                    queryClient.invalidateQueries({ queryKey: ["activity", activeTabId] });
                    queryClient.invalidateQueries({ queryKey: ["entity-list", activeTabId] });
                    queryClient.invalidateQueries({ queryKey: ["investigations"] });
                    setTimeout(() => setIsSpinning(false), 1000);
                  }}
                  className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
                  title="Refresh status"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", (isSpinning || investigation.isFetching || status.isFetching) && "animate-spin")} />
                </button>

                <button
                  onClick={() => setDeleteConfirmOpen(true)}
                  className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-red-500/15 hover:text-red-400 transition-colors"
                  title="Delete Investigation"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* GROUP 4 & 5: VIEW & UTILS */}
          <div className="flex items-center gap-1.5 ml-auto">
            {activeTabId && (
              <>
                <div className="flex items-center gap-1 border-r border-[var(--nx-border)] pr-2">
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

                  <button
                    onClick={triggerFit}
                    className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
                    title="Fit to Canvas (Space)"
                  >
                    <Maximize2 className="h-3 w-3" />
                    <span>Fit</span>
                  </button>
                </div>

                <div className="flex items-center gap-0.5 border-r border-[var(--nx-border)] pr-2">
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
                </div>
              </>
            )}

            <div className="flex items-center pl-2 mr-1">
              <button
                onClick={() => setReportModalOpen(true)}
                className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs font-medium text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
                title="Generate Reports"
              >
                <FileDown className="h-3.5 w-3.5" />
                <span>Reports</span>
              </button>
            </div>

            <div className="flex items-center gap-1 pl-1">
              <button
                onClick={toggleTheme}
                className="flex h-7 w-7 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-primary)] transition-colors"
                title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
                aria-label={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
              >
                {theme === "dark" ? (
                  <Sun className="h-3.5 w-3.5 text-amber-400" />
                ) : (
                  <Moon className="h-3.5 w-3.5 text-sky-600" />
                )}
              </button>

              <Link
                to="/settings"
                className="flex h-7 w-7 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-2)] hover:text-[var(--nx-text-primary)] transition-colors"
                title="Settings"
                aria-label="Settings"
              >
                <Settings className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleDelete}
        title="Delete Investigation"
        message={`Permanently delete investigation "${inv?.name ?? ""}" and all its data? This action cannot be undone.`}
        confirmLabel="Delete"
        loading={deleteInv.isPending}
      />
      <ReportGeneratorModal
        open={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
      />
    </header>
  );
}
