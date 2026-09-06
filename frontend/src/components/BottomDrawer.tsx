import {
  Activity,
  Brain,
  FileText,
  Settings,
  ChevronDown,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { TimelinePanel } from "./TimelinePanel";
import { AIAnalysisPanel } from "./AIAnalysisPanel";
import { ReportsPanel } from "./ReportsPanel";
import SettingsPanel from "./SettingsPanel";
import { cn } from "../lib/utils";

interface BottomDrawerProps {
  investigationId: string;
}

export function BottomDrawer({ investigationId }: BottomDrawerProps) {
  const bottomDrawerOpen = useWorkspaceStore((s) => s.bottomDrawerOpen);
  const toggleBottomDrawer = useWorkspaceStore((s) => s.toggleBottomDrawer);
  const bottomTab = useWorkspaceStore((s) => s.bottomTab);
  const setBottomTab = useWorkspaceStore((s) => s.setBottomTab);

  if (!bottomDrawerOpen) return null;

  return (
    <div className="flex h-60 shrink-0 flex-col border-t border-[var(--nx-border)] bg-[var(--nx-surface-1)] z-20">
      {/* Drawer Tab Header */}
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 select-none">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setBottomTab("timeline")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "timeline"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Activity & Observations</span>
          </button>

          <button
            onClick={() => setBottomTab("ai")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "ai"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <Brain className="h-3.5 w-3.5" />
            <span>AI Intelligence</span>
          </button>

          <button
            onClick={() => setBottomTab("reports")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "reports"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Reports & Export</span>
          </button>

          <button
            onClick={() => setBottomTab("settings")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "settings"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <Settings className="h-3.5 w-3.5" />
            <span>Settings</span>
          </button>
        </div>

        <button
          onClick={toggleBottomDrawer}
          className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
          title="Minimize drawer"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {bottomTab === "timeline" && (
          <TimelinePanel investigationId={investigationId} />
        )}
        {bottomTab === "ai" && (
          <AIAnalysisPanel investigationId={investigationId} />
        )}
        {bottomTab === "reports" && (
          <ReportsPanel investigationId={investigationId} />
        )}
        {bottomTab === "settings" && <SettingsPanel />}
      </div>
    </div>
  );
}
