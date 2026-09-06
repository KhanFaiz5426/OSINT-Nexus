import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { useInvestigation } from "../hooks/useApi";
import { useWorkspaceStore } from "../store/workspace";
import { InvestigationHeader } from "../components/InvestigationHeader";
import { EntityListPanel } from "../components/EntityListPanel";
import { GraphView } from "../components/GraphView";
import { GraphLegend } from "../components/GraphLegend";
import { EntityDetailPanel } from "../components/EntityDetailPanel";
import { AIAnalysisPanel } from "../components/AIAnalysisPanel";
import { ReportsPanel } from "../components/ReportsPanel";
import { TimelinePanel } from "../components/TimelinePanel";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { Link } from "react-router-dom";
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  ChevronDown,
  ChevronUp,
  Brain,
  FileText,
  Clock,
} from "lucide-react";
import { cn } from "../lib/utils";

type RightTab = "inspector" | "ai" | "reports";
type BottomTab = "timeline" | "reports";

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const investigationId = id ?? "";
  const investigation = useInvestigation(investigationId);
  const resetWorkspace = useWorkspaceStore((s) => s.resetWorkspace);
  const selectedEntityId = useWorkspaceStore((s) => s.selectedEntityId);

  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [bottomOpen, setBottomOpen] = useState(true);
  const [rightTab, setRightTab] = useState<RightTab>("inspector");
  const [bottomTab, setBottomTab] = useState<BottomTab>("timeline");

  // Auto-switch to inspector when an entity is selected
  useEffect(() => {
    if (selectedEntityId) {
      setRightTab("inspector");
      setRightOpen(true);
    }
  }, [selectedEntityId]);

  // Reset workspace when changing investigations.
  useEffect(() => {
    return () => resetWorkspace();
  }, [investigationId, resetWorkspace]);

  if (investigation.isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingState rows={2} />
      </div>
    );
  }

  if (investigation.error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <ErrorState
          message="Investigation not found."
          onRetry={() => investigation.refetch()}
        />
        <Link
          to="/investigations"
          className="text-sm text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors"
        >
          ← Back to investigations
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Investigation toolbar */}
      <InvestigationHeader investigationId={investigationId} />

      {/* Main workspace */}
      <div className="flex min-h-0 flex-1">
        {/* Left panel: entities */}
        {leftOpen && (
          <div className="flex w-[280px] shrink-0 flex-col border-r border-[var(--nx-border)]">
            <EntityListPanel investigationId={investigationId} />
          </div>
        )}

        {/* Center: graph canvas */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Graph toolbar */}
          <div className="flex shrink-0 items-center gap-1 border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-2 py-1">
            <button
              onClick={() => setLeftOpen(!leftOpen)}
              className="flex h-6 w-6 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              title={leftOpen ? "Hide entities" : "Show entities"}
            >
              {leftOpen ? (
                <PanelLeftClose className="h-3.5 w-3.5" />
              ) : (
                <PanelLeftOpen className="h-3.5 w-3.5" />
              )}
            </button>
            <div className="flex-1" />
            <button
              onClick={() => setBottomOpen(!bottomOpen)}
              className="flex h-6 w-6 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              title={bottomOpen ? "Hide timeline" : "Show timeline"}
            >
              {bottomOpen ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronUp className="h-3.5 w-3.5" />
              )}
            </button>
            <button
              onClick={() => setRightOpen(!rightOpen)}
              className="flex h-6 w-6 items-center justify-center rounded text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              title={rightOpen ? "Hide inspector" : "Show inspector"}
            >
              {rightOpen ? (
                <PanelRightClose className="h-3.5 w-3.5" />
              ) : (
                <PanelRightOpen className="h-3.5 w-3.5" />
              )}
            </button>
          </div>

          {/* Graph + bottom panel */}
          <div className="flex min-h-0 flex-1 flex-col">
            {/* Graph area */}
            <div className="relative min-h-[200px] flex-1">
              <GraphView investigationId={investigationId} />
              <GraphLegend investigationId={investigationId} />
            </div>

            {/* Bottom panel: timeline/reports */}
            {bottomOpen && (
              <div className="flex h-[200px] shrink-0 flex-col border-t border-[var(--nx-border)]">
                <div className="flex shrink-0 items-center border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)]">
                  <button
                    onClick={() => setBottomTab("timeline")}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                      bottomTab === "timeline"
                        ? "border-b-2 border-[var(--nx-accent)] text-[var(--nx-accent)]"
                        : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                    )}
                  >
                    <Clock className="h-3 w-3" />
                    Timeline
                  </button>
                  <button
                    onClick={() => setBottomTab("reports")}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                      bottomTab === "reports"
                        ? "border-b-2 border-[var(--nx-accent)] text-[var(--nx-accent)]"
                        : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                    )}
                  >
                    <FileText className="h-3 w-3" />
                    Reports
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-auto">
                  {bottomTab === "timeline" && (
                    <TimelinePanel investigationId={investigationId} />
                  )}
                  {bottomTab === "reports" && (
                    <ReportsPanel investigationId={investigationId} />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right panel: inspector / AI / reports */}
        {rightOpen && (
          <div className="flex w-[320px] shrink-0 flex-col border-l border-[var(--nx-border)]">
            {/* Right panel tabs */}
            <div className="flex shrink-0 items-center border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)]">
              <button
                onClick={() => setRightTab("inspector")}
                className={cn(
                  "px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                  rightTab === "inspector"
                    ? "border-b-2 border-[var(--nx-accent)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
              >
                Inspector
              </button>
              <button
                onClick={() => setRightTab("ai")}
                className={cn(
                  "flex items-center gap-1 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                  rightTab === "ai"
                    ? "border-b-2 border-[var(--nx-accent)] text-[var(--nx-accent)]"
                    : "text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)]",
                )}
              >
                <Brain className="h-3 w-3" />
                AI
              </button>
            </div>
            {/* Right panel content */}
            <div className="min-h-0 flex-1 overflow-auto">
              {rightTab === "inspector" && (
                <EntityDetailPanel investigationId={investigationId} />
              )}
              {rightTab === "ai" && (
                <AIAnalysisPanel investigationId={investigationId} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
