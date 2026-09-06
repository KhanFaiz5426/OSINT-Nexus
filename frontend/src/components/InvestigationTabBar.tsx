import {
  Plus,
  X,
  Globe,
  MonitorSmartphone,
  Link2,
  Mail,
  User,
  Building2,
  HelpCircle,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
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

export function InvestigationTabBar() {
  const openTabs = useWorkspaceStore((s) => s.openTabs);
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab);
  const closeTab = useWorkspaceStore((s) => s.closeTab);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);

  return (
    <div className="flex h-8 shrink-0 items-center border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-1 select-none overflow-x-auto no-scrollbar">
      {/* Quick Add Button */}
      <button
        onClick={() => setNewModalOpen(true)}
        className="flex h-6 w-6 items-center justify-center rounded text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-accent)] transition-colors mr-1 shrink-0"
        title="New Investigation Workspace (Ctrl+N)"
      >
        <Plus className="h-3.5 w-3.5" />
      </button>

      {/* Tabs */}
      {openTabs.length === 0 ? (
        <span className="text-[11px] text-[var(--nx-text-muted)] italic px-2">
          No investigation workspaces open. Click [+] or "Open..." to start.
        </span>
      ) : (
        <div className="flex items-center gap-0.5 h-full">
          {openTabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            const IconComponent = TARGET_ICONS[tab.target_type] ?? HelpCircle;

            return (
              <div
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                onAuxClick={(e) => {
                  if (e.button === 1) {
                    // Middle click to close tab
                    e.preventDefault();
                    closeTab(tab.id);
                  }
                }}
                className={cn(
                  "group relative flex h-full items-center gap-1.5 px-3 text-xs font-medium cursor-pointer transition-all border-r border-[var(--nx-border)] shrink-0 max-w-[200px]",
                  isActive
                    ? "bg-[var(--nx-surface-2)] text-[var(--nx-text-primary)]"
                    : "bg-[var(--nx-surface-1)] text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)]",
                )}
                title={`${tab.target} (${tab.target_type})`}
              >
                {/* Active Indicator line */}
                {isActive && (
                  <span className="absolute inset-x-0 top-0 h-[2px] bg-[var(--nx-accent)]" />
                )}

                {/* Target Type Icon */}
                <IconComponent
                  className={cn(
                    "h-3 w-3 shrink-0",
                    isActive ? "text-[var(--nx-accent)]" : "text-[var(--nx-text-muted)]",
                  )}
                />

                {/* Tab Label */}
                <span className="truncate font-mono text-[11px]">
                  {tab.target || tab.name || "Untitled"}
                </span>

                {/* Status Dot */}
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full shrink-0",
                    tab.status === "running" && "bg-amber-400 animate-pulse",
                    tab.status === "completed" && "bg-emerald-400",
                    tab.status === "error" && "bg-rose-400",
                    (!tab.status || tab.status === "created") && "bg-[var(--nx-accent)]/60",
                    tab.status === "stopped" && "bg-[var(--nx-text-muted)]",
                  )}
                />

                {/* Close Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(tab.id);
                  }}
                  className="ml-1 rounded p-0.5 text-[var(--nx-text-muted)] opacity-0 group-hover:opacity-100 hover:bg-[var(--nx-surface-4)] hover:text-[var(--nx-text-primary)] transition-all"
                  title="Close Workspace"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
