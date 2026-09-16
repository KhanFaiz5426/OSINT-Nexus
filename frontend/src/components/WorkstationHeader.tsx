import {
  Crosshair,
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
  Loader2,
  Check,
  FileText,
  File,
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
  useGenerateReport,
  useInvestigationSSE,
} from "../hooks/useApi";
import { reportsApi, type ReportFormat } from "../api/investigations";
import { statusBadgeClass } from "../lib/format";
import { Spinner } from "./LoadingState";
import { ConfirmDialog } from "./ConfirmDialog";
import { cn } from "../lib/utils";

export function WorkstationHeader() {
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);
  const queryClient = useQueryClient();

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
  const [reportsDropdownOpen, setReportsDropdownOpen] = useState(false);
  const reportsDropdownRef = useRef<HTMLDivElement>(null);

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

  // Close reports dropdown on outside click
  useEffect(() => {
    if (!reportsDropdownOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (reportsDropdownRef.current && !reportsDropdownRef.current.contains(e.target as Node)) {
        setReportsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [reportsDropdownOpen]);

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
          <div className="flex h-6 w-6 items-center justify-center rounded bg-[var(--nx-surface-1)]">
            <img src="/osint-nexus-logo.svg" alt="Logo" className="h-5 w-5" />
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
                // Also invalidate graph, activity, and entity data
                queryClient.invalidateQueries({ queryKey: ["graph", activeTabId] });
                queryClient.invalidateQueries({ queryKey: ["activity", activeTabId] });
                queryClient.invalidateQueries({ queryKey: ["entity-list", activeTabId] });
              }}
              className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              title="Refresh status"
            >
              <RefreshCw className="h-3 w-3" />
            </button>

            <button
              onClick={() => setDeleteConfirmOpen(true)}
              className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-red-500/15 hover:text-red-400 transition-colors"
              title="Delete Investigation"
            >
              <Trash2 className="h-3 w-3" />
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

            {/* Reports Dropdown */}
            <ReportsDropdown
              investigationId={activeTabId}
              open={reportsDropdownOpen}
              setOpen={setReportsDropdownOpen}
              dropdownRef={reportsDropdownRef}
            />

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
            </div>

            <div className="h-4 w-px bg-[var(--nx-border)] mx-1" />
          </>
        )}

        {/* Settings link */}
        <Link
          to="/settings"
          className="flex h-7 w-7 items-center justify-center rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          title="Settings"
          aria-label="Settings"
        >
          <Settings className="h-3.5 w-3.5" />
        </Link>

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

      <ConfirmDialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleDelete}
        title="Delete Investigation"
        message={`Permanently delete investigation "${inv?.name ?? ""}" and all its data? This action cannot be undone.`}
        confirmLabel="Delete"
        loading={deleteInv.isPending}
      />
    </header>
  );
}

/* ─── Reports Dropdown Component ─────────────────────────────────────────── */

function ReportsDropdown({
  investigationId,
  open,
  setOpen,
  dropdownRef,
}: {
  investigationId: string;
  open: boolean;
  setOpen: (v: boolean) => void;
  dropdownRef: React.RefObject<HTMLDivElement | null>;
}) {
  const generateReport = useGenerateReport();
  const [generatingFormat, setGeneratingFormat] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  const handleGenerate = async (format: ReportFormat) => {
    setGeneratingFormat(format);
    setLastSuccess(null);
    try {
      const report = await generateReport.mutateAsync({
        investigationId,
        format,
      });
      // Auto-download using fetch to ensure correct filename/content-type.
      const downloadUrl = reportsApi.downloadUrl(investigationId, report.id);
      const res = await fetch(downloadUrl);
      const blob = await res.blob();
      const ext = report.format || format;
      const filename = `report.${ext}`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setLastSuccess(ext);
      setTimeout(() => {
        setLastSuccess(null);
        setOpen(false);
      }, 1500);
    } catch {
      // Error displayed via generateReport.isError
    } finally {
      setGeneratingFormat(null);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 py-1 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
        title="Export & Reports"
      >
        <FileDown className="h-3 w-3" />
        <span>Reports</span>
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-52 rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] py-1 shadow-xl">
          <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
            Download Report
          </div>

          {/* PDF */}
          <button
            onClick={() => handleGenerate("pdf")}
            disabled={generatingFormat !== null}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors disabled:opacity-50"
          >
            {generatingFormat === "pdf" ? (
              <Loader2 className="h-4 w-4 animate-spin text-red-400" />
            ) : lastSuccess === "pdf" ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <File className="h-4 w-4 text-red-400" />
            )}
            <div className="flex flex-col items-start">
              <span className="font-medium">Download PDF</span>
              <span className="text-[10px] text-[var(--nx-text-muted)]">
                Full investigation report
              </span>
            </div>
          </button>

          {/* HTML */}
          <button
            onClick={() => handleGenerate("html")}
            disabled={generatingFormat !== null}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-xs text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors disabled:opacity-50"
          >
            {generatingFormat === "html" ? (
              <Loader2 className="h-4 w-4 animate-spin text-sky-400" />
            ) : lastSuccess === "html" ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <FileText className="h-4 w-4 text-sky-400" />
            )}
            <div className="flex flex-col items-start">
              <span className="font-medium">Download HTML</span>
              <span className="text-[10px] text-[var(--nx-text-muted)]">
                Web-viewable report
              </span>
            </div>
          </button>

          {generateReport.isError && (
            <div className="px-3 py-1.5 text-[10px] text-red-400">
              {generateReport.error.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
