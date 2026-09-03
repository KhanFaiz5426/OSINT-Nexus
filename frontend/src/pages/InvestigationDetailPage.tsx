import { Link, useParams } from "react-router-dom";
import { useEffect } from "react";
import { useInvestigation } from "../hooks/useApi";
import { useWorkspaceStore } from "../store/workspace";
import { InvestigationHeader } from "../components/InvestigationHeader";
import { EntityListPanel } from "../components/EntityListPanel";
import { GraphView } from "../components/GraphView";
import { GraphLegend } from "../components/GraphLegend";
import { EntityDetailPanel } from "../components/EntityDetailPanel";
import { AIAnalysisPanel } from "../components/AIAnalysisPanel";
import { TimelinePanel } from "../components/TimelinePanel";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const investigationId = id ?? "";
  const investigation = useInvestigation(investigationId);
  const resetWorkspace = useWorkspaceStore((s) => s.resetWorkspace);

  // Reset workspace when changing investigations.
  useEffect(() => {
    return () => resetWorkspace();
  }, [investigationId, resetWorkspace]);

  if (investigation.isLoading) {
    return (
      <div className="mx-auto max-w-7xl">
        <LoadingState rows={2} />
      </div>
    );
  }

  if (investigation.error) {
    return (
      <div className="mx-auto max-w-3xl">
        <ErrorState
          message="Investigation not found."
          onRetry={() => investigation.refetch()}
        />
        <div className="mt-4">
          <Link
            to="/investigations"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            ← Back to investigations
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-[1600px] flex-col gap-3">
      <div className="flex items-center justify-between">
        <Link
          to="/investigations"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← All Investigations
        </Link>
      </div>

      <InvestigationHeader investigationId={investigationId} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-12">
        {/* Left column: entities */}
        <div className="flex min-h-0 flex-col gap-3 lg:col-span-3">
          <div className="min-h-[280px] flex-1 lg:max-h-[60vh]">
            <EntityListPanel investigationId={investigationId} />
          </div>
        </div>

        {/* Center column: graph + legend */}
        <div className="flex min-h-[400px] flex-col gap-3 lg:col-span-6">
          <div className="flex shrink-0 items-center gap-2">
            <GraphLegend investigationId={investigationId} />
          </div>
          <div className="min-h-0 flex-1">
            <GraphView investigationId={investigationId} />
          </div>
        </div>

        {/* Right column: entity inspector + AI */}
        <div className="flex min-h-0 flex-col gap-3 lg:col-span-3">
          <div className="min-h-[360px] flex-[2]">
            <EntityDetailPanel investigationId={investigationId} />
          </div>
          <div className="min-h-[200px] flex-1">
            <AIAnalysisPanel investigationId={investigationId} />
          </div>
        </div>
      </div>

      <div className="min-h-[180px]">
        <TimelinePanel investigationId={investigationId} />
      </div>
    </div>
  );
}
