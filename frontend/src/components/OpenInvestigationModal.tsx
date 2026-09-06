import { useState, useEffect } from "react";
import {
  FolderOpen,
  X,
  Search,
  Globe,
  MonitorSmartphone,
  Link2,
  Mail,
  User,
  Building2,
  HelpCircle,
  ExternalLink,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { useInvestigations } from "../hooks/useApi";
import { statusBadgeClass, formatRelativeTime } from "../lib/format";
import { LoadingState } from "./LoadingState";
import { cn } from "../lib/utils";

const TARGET_ICONS: Record<string, typeof Globe> = {
  domain: Globe,
  ip: MonitorSmartphone,
  url: Link2,
  email: Mail,
  username: User,
  organization: Building2,
  unknown: HelpCircle,
};

export function OpenInvestigationModal() {
  const openModalOpen = useWorkspaceStore((s) => s.openModalOpen);
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);
  const openTab = useWorkspaceStore((s) => s.openTab);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: investigations, isLoading, error } = useInvestigations();

  // Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && openModalOpen) {
        setOpenModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [openModalOpen, setOpenModalOpen]);

  if (!openModalOpen) return null;

  const filtered = (investigations ?? []).filter((inv) => {
    const matchesQuery =
      inv.target.toLowerCase().includes(query.toLowerCase()) ||
      inv.name.toLowerCase().includes(query.toLowerCase());
    const matchesStatus =
      statusFilter === "all" || inv.status === statusFilter;
    return matchesQuery && matchesStatus;
  });

  const handleSelect = (inv: {
    id: string;
    target: string;
    name: string;
    target_type: string;
    status: string;
  }) => {
    openTab({
      id: inv.id,
      target: inv.target,
      name: inv.name,
      target_type: inv.target_type,
      status: inv.status,
    });
    setOpenModalOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div
        className="flex flex-col w-full max-w-2xl max-h-[80vh] rounded-lg border border-[var(--nx-border-strong)] bg-[var(--nx-surface-1)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--nx-border)] px-4 py-3 bg-[var(--nx-surface-2)] shrink-0">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)]">
              <FolderOpen className="h-3.5 w-3.5" />
            </div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-primary)]">
              Open Investigation Workspace
            </h2>
          </div>
          <button
            onClick={() => setOpenModalOpen(false)}
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Search & Filter Bar */}
        <div className="p-3 border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] shrink-0 space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--nx-text-muted)]" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by target or investigation name..."
              autoFocus
              className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] pl-8 pr-3 py-1.5 text-xs text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent)] focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-1 text-[11px]">
            {["all", "running", "completed", "created", "error"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={cn(
                  "rounded px-2 py-0.5 capitalize transition-colors",
                  statusFilter === st
                    ? "bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)] font-medium"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* List Content */}
        <div className="flex-1 overflow-y-auto p-2 divide-y divide-[var(--nx-border)]/50 min-h-[250px]">
          {isLoading && (
            <div className="p-6">
              <LoadingState rows={3} label="Loading investigations..." />
            </div>
          )}

          {error && (
            <div className="p-6 text-center text-xs text-rose-400">
              Failed to load investigations.
            </div>
          )}

          {!isLoading && !error && filtered.length === 0 && (
            <div className="p-12 text-center text-xs text-[var(--nx-text-muted)]">
              {query ? "No investigations matched your search." : "No saved investigations found."}
            </div>
          )}

          {!isLoading &&
            filtered.map((inv) => {
              const IconComponent = TARGET_ICONS[inv.target_type] ?? HelpCircle;

              return (
                <div
                  key={inv.id}
                  onClick={() => handleSelect(inv)}
                  className="flex items-center justify-between p-2.5 rounded hover:bg-[var(--nx-surface-2)] cursor-pointer transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-[var(--nx-surface-3)] border border-[var(--nx-border)] text-[var(--nx-accent)]">
                      <IconComponent className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-xs font-mono font-medium text-[var(--nx-text-primary)]">
                          {inv.target}
                        </span>
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.2 text-[9px] font-semibold uppercase tracking-wider",
                            statusBadgeClass(inv.status),
                          )}
                        >
                          {inv.status}
                        </span>
                      </div>
                      <p className="truncate text-[11px] text-[var(--nx-text-muted)]">
                        {inv.name} · {inv.depth} depth
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className="text-[10px] font-mono text-[var(--nx-text-muted)]">
                      {formatRelativeTime(inv.created_at)}
                    </span>
                    <button className="flex items-center gap-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2 py-1 text-[11px] text-[var(--nx-text-secondary)] group-hover:border-[var(--nx-accent)] group-hover:text-[var(--nx-accent)] transition-colors">
                      <span>Open</span>
                      <ExternalLink className="h-2.5 w-2.5" />
                    </button>
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
