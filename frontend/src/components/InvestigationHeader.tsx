import {
  Play,
  Square,
  RefreshCw,
  Target,
  AlertCircle,
  ChevronLeft,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  useInvestigation,
  useInvestigationStatus,
  useStartInvestigation,
  useStopInvestigation,
} from "../hooks/useApi";
import {
  cn,
} from "../lib/utils";
import { statusBadgeClass } from "../lib/format";
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
    <div className="flex items-center gap-3 border-b border-[var(--nx-border)] bg-[var(--nx-surface-1)] px-4 py-2">
      {/* Back button */}
      <Link
        to="/investigations"
        className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
        title="All Investigations"
      >
        <ChevronLeft className="h-4 w-4" />
      </Link>

      {investigation.isLoading && (
        <div className="flex items-center gap-2 text-sm text-[var(--nx-text-tertiary)]">
          <Spinner className="h-3.5 w-3.5" /> Loading...
        </div>
      )}
      {investigation.error && (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          Failed to load investigation.
        </div>
      )}

      {inv && (
        <>
          {/* Name + status */}
          <div className="flex items-center gap-2.5 min-w-0">
            <h1 className="truncate text-sm font-semibold text-[var(--nx-text-primary)]">
              {inv.name}
            </h1>
            <span
              className={cn(
                "inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                statusBadgeClass(st?.status ?? inv.status),
              )}
            >
              {isRunning && <Spinner className="h-2.5 w-2.5" />}
              {st?.status ?? inv.status}
            </span>
          </div>

          {/* Target + meta */}
          <div className="hidden items-center gap-2 text-[11px] text-[var(--nx-text-tertiary)] md:flex">
            <span className="inline-flex items-center gap-1">
              <Target className="h-3 w-3 text-[var(--nx-text-muted)]" />
              <span className="font-mono text-[var(--nx-text-secondary)]">{inv.target}</span>
            </span>
            <span className="text-[var(--nx-border-strong)]">·</span>
            <span className="rounded bg-[var(--nx-surface-3)] px-1.5 py-0.5 text-[10px] uppercase">
              {inv.target_type}
            </span>
            <span className="text-[var(--nx-border-strong)]">·</span>
            <span className="rounded bg-[var(--nx-surface-3)] px-1.5 py-0.5 text-[10px]">
              {inv.depth}
            </span>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Stats (compact) */}
          {st && (
            <div className="hidden items-center gap-4 lg:flex">
              <InlineStat label="Entities" value={st.entity_count} />
              <InlineStat label="Rels" value={st.relationship_count} />
              <InlineStat
                label="API"
                value={`${st.api_calls_used}/${st.api_budget}`}
              />
              {/* Budget bar */}
              <div className="flex items-center gap-1.5">
                <div className="h-1 w-16 overflow-hidden rounded-full bg-[var(--nx-surface-3)]">
                  <div
                    className="h-full rounded-full bg-[var(--nx-accent)] transition-all"
                    style={{
                      width: `${Math.min(100, (st.api_calls_used / Math.max(1, st.api_budget)) * 100)}%`,
                    }}
                  />
                </div>
                <span className="text-[10px] font-mono text-[var(--nx-text-muted)] tabular-nums">
                  {Math.round((st.api_calls_used / Math.max(1, st.api_budget)) * 100)}%
                </span>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-1.5">
            {(isStartable || isFinished) && (
              <button
                onClick={onStart}
                disabled={start.isPending}
                className="inline-flex items-center gap-1 rounded-md bg-[var(--nx-accent)] px-2.5 py-1 text-xs font-medium text-[var(--nx-base)] hover:brightness-110 disabled:opacity-50 transition-all"
              >
                {start.isPending ? (
                  <Spinner className="h-3 w-3" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                {isFinished ? "Re-run" : "Start"}
              </button>
            )}
            {isStoppable && (
              <button
                onClick={onStop}
                disabled={stop.isPending}
                className="inline-flex items-center gap-1 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-all"
              >
                {stop.isPending ? (
                  <Spinner className="h-3 w-3" />
                ) : (
                  <Square className="h-3 w-3" />
                )}
                Stop
              </button>
            )}
            <button
              onClick={() => {
                investigation.refetch();
                status.refetch();
              }}
              className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-secondary)] transition-colors"
              aria-label="Refresh status"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}

      {/* Inline errors */}
      {start.isError && (
        <div className="absolute left-1/2 top-full z-50 mt-1 -translate-x-1/2 rounded-md border border-red-500/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 shadow-lg">
          Failed to start: {start.error.message}
        </div>
      )}
      {stop.isError && (
        <div className="absolute left-1/2 top-full z-50 mt-1 -translate-x-1/2 rounded-md border border-red-500/25 bg-red-500/10 px-3 py-1.5 text-xs text-red-400 shadow-lg">
          Failed to stop: {stop.error.message}
        </div>
      )}
    </div>
  );
}

function InlineStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-[var(--nx-text-muted)]">
        {label}
      </span>
      <span className="text-xs font-mono font-medium tabular-nums text-[var(--nx-text-secondary)]">
        {value}
      </span>
    </div>
  );
}
