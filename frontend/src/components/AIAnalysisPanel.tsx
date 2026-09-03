import { Brain, ShieldAlert, Lightbulb, AlertTriangle } from "lucide-react";
import { useAIAnalysis } from "../hooks/useApi";
import { Panel } from "./Panel";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { riskBadgeClass } from "../lib/format";
import { cn } from "../lib/utils";
import { useWorkspaceStore } from "../store/workspace";

export function AIAnalysisPanel({
  investigationId,
}: {
  investigationId: string;
}) {
  const { data, isLoading, error, refetch } = useAIAnalysis(investigationId);
  const selectEntity = useWorkspaceStore((s) => s.selectEntity);

  if (error) {
    return (
      <Panel title="AI Analysis">
        <ErrorState
          message="Failed to load AI analysis."
          onRetry={() => refetch()}
        />
      </Panel>
    );
  }

  if (isLoading || !data) {
    return (
      <Panel title="AI Analysis">
        <LoadingState label="Generating analysis..." rows={3} />
      </Panel>
    );
  }

  const analyzer = data.analyzer_output;
  const hasGraph = data.graph_summary.entity_count > 0;

  if (!hasGraph) {
    return (
      <Panel title="AI Analysis">
        <EmptyState
          icon={<Brain className="h-10 w-10" />}
          title="No analysis available yet"
          description="Run the investigation to populate the knowledge graph and generate insights."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="AI Analysis"
      actions={
        <span className="text-[10px] text-gray-400">
          {data.pivot_rounds_completed} pivot rounds
        </span>
      }
    >
      {!analyzer && (
        <p className="text-sm text-gray-500">
          Analysis is unavailable for this investigation.
        </p>
      )}
      {analyzer && (
        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
                  riskBadgeClass(analyzer.risk_level),
                )}
              >
                {analyzer.risk_level} risk
              </span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-gray-800">
              {analyzer.summary}
            </p>
            {analyzer.risk_reasoning && (
              <p className="mt-1 text-xs text-gray-500">
                {analyzer.risk_reasoning}
              </p>
            )}
          </div>

          {analyzer.key_findings.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-700">
                <Lightbulb className="h-3.5 w-3.5" />
                Key Findings ({analyzer.key_findings.length})
              </h3>
              <ul className="space-y-2">
                {analyzer.key_findings.map((f, i: number) => (
                  <li
                    key={i}
                    className="rounded-md border border-gray-200 bg-gray-50 p-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-medium text-gray-900">
                        {f.title}
                      </h4>
                      <span className="shrink-0 text-xs tabular-nums text-gray-500">
                        {(f.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-gray-700">
                      {f.description}
                    </p>
                    {f.entity_ids.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {f.entity_ids.slice(0, 5).map((eid: string) => (
                          <button
                            key={eid}
                            onClick={() => selectEntity(eid)}
                            className="rounded bg-white px-1.5 py-0.5 font-mono text-[10px] text-blue-600 ring-1 ring-gray-300 hover:bg-blue-50"
                          >
                            {eid}
                          </button>
                        ))}
                        {f.entity_ids.length > 5 && (
                          <span className="text-[10px] text-gray-400">
                            +{f.entity_ids.length - 5} more
                          </span>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {analyzer.recommendations.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-700">
                <ShieldAlert className="h-3.5 w-3.5" />
                Recommendations
              </h3>
              <ul className="space-y-1 text-sm text-gray-800">
                {analyzer.recommendations.map((r: string, i: number) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 rounded-md border border-gray-200 bg-white p-2"
                  >
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="mt-4 border-t border-gray-100 pt-3 text-[10px] text-gray-400">
        {data.graph_summary.entity_count} entities ·{" "}
        {data.graph_summary.relationship_count} relationships ·{" "}
        Generated {data.generated_at ? new Date(data.generated_at).toLocaleString() : "—"}
      </div>
    </Panel>
  );
}
