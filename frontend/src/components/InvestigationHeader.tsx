import {
  Play,
  Square,
  RefreshCw,
  Target,
  AlertCircle,
  Cpu,
} from "lucide-react";
import {
  useInvestigation,
  useInvestigationStatus,
  useStartInvestigation,
  useStopInvestigation,
} from "../hooks/useApi";
import {
  cn,
} from "../lib/utils";
import { formatRelativeTime, statusBadgeClass } from "../lib/format";
import { Spinner } from "./LoadingState";

interface Props {
  investigationId: string;
}

export function InvestigationHeader({ investigationId }: Props) {
  const investigation = useInvestigation(investigationId);
  const status = useInvestigationStatus(investigationId, {
    refetchInterval: 3_000,
  });
  const start = useStartInvestigation();
  const stop = useStopInvestigation();

  const inv = investigation.data;
  const st = status.data;

  const onStart = () => {
    start.mutate(investigationId);
  };
  const onStop = () => {
    stop.mutate(investigationId);
  };

  const isRunning = st?.status === "running";
  const isStartable = st?.status === "created";
  const isStoppable = st?.status === "running";
  const isFinished = ["completed", "stopped", "error"].includes(
    st?.status ?? "",
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white px-5 py-4 shadow-sm">
      {investigation.isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Spinner /> Loading investigation...
        </div>
      )}
      {investigation.error && (
        <div className="flex items-center gap-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" />
          Failed to load investigation.
        </div>
      )}
      {inv && (
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h1 className="truncate text-xl font-semibold text-gray-900">
                {inv.name}
              </h1>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
                  statusBadgeClass(st?.status ?? inv.status),
                )}
              >
                {isRunning && <Spinner className="h-3 w-3" />}
                {st?.status ?? inv.status}
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600">
              <span className="inline-flex items-center gap-1">
                <Target className="h-3.5 w-3.5 text-gray-400" />
                <span className="font-mono">{inv.target}</span>
              </span>
              <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-xs">
                {inv.target_type}
              </span>
              <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-xs">
                depth: {inv.depth}
              </span>
              <span className="text-xs text-gray-400">
                updated {formatRelativeTime(inv.updated_at)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {(isStartable || isFinished) && (
              <button
                onClick={onStart}
                disabled={start.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {start.isPending ? (
                  <Spinner className="h-3.5 w-3.5" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                {isFinished ? "Re-run" : "Start"}
              </button>
            )}
            {isStoppable && (
              <button
                onClick={onStop}
                disabled={stop.isPending}
                className="inline-flex items-center gap-1.5 rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
              >
                {stop.isPending ? (
                  <Spinner className="h-3.5 w-3.5" />
                ) : (
                  <Square className="h-3.5 w-3.5" />
                )}
                Stop
              </button>
            )}
            <button
              onClick={() => {
                investigation.refetch();
                status.refetch();
              }}
              className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              aria-label="Refresh status"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {st && (
        <div className="mt-4 grid grid-cols-2 gap-3 border-t border-gray-100 pt-3 sm:grid-cols-5">
          <Stat label="Entities" value={st.entity_count} />
          <Stat label="Relationships" value={st.relationship_count} />
          <Stat
            label="API calls"
            value={`${st.api_calls_used}/${st.api_budget}`}
          />
          <Stat
            label="Budget"
            value={`${Math.round((st.api_calls_used / Math.max(1, st.api_budget)) * 100)}%`}
            progress={(st.api_calls_used / Math.max(1, st.api_budget)) * 100}
            color="bg-blue-500"
          />
          <Stat
            label="Status"
            value={st.status}
            icon={<Cpu className="h-3.5 w-3.5" />}
          />
        </div>
      )}

      {start.isError && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Failed to start investigation: {start.error.message}
        </div>
      )}
      {stop.isError && (
        <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Failed to stop investigation: {stop.error.message}
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  progress,
  color,
  icon,
}: {
  label: string;
  value: string | number;
  progress?: number;
  color?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-gray-500">
        {icon}
        {label}
      </div>
      <div className="mt-0.5 font-mono text-base font-semibold tabular-nums text-gray-900">
        {value}
      </div>
      {progress !== undefined && (
        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={cn("h-full transition-all", color ?? "bg-blue-500")}
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      )}
    </div>
  );
}
