import { Link } from "react-router-dom";
import { useInvestigations } from "../hooks/useApi";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { statusBadgeClass, formatRelativeTime } from "../lib/format";
import { cn } from "../lib/utils";
import type { Investigation } from "../api/investigations";
import { Plus, Crosshair, Activity, GitBranch, AlertCircle, CheckCircle2 } from "lucide-react";

export function DashboardPage() {
  const { data, isLoading, error } = useInvestigations({ limit: 5 });

  const total = data?.length ?? 0;
  const running = data?.filter((i) => i.status === "running").length ?? 0;
  const completed = data?.filter((i) => i.status === "completed").length ?? 0;
  const errors = data?.filter((i) => i.status === "error").length ?? 0;
  const totalEntities = data?.reduce((s, i) => s + i.entity_count, 0) ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-2">
      {/* Header with CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--nx-text-primary)]">Dashboard</h1>
          <p className="mt-0.5 text-sm text-[var(--nx-text-muted)]">
            Investigation overview and quick actions
          </p>
        </div>
        <Link
          to="/investigations/new"
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--nx-accent)] px-4 py-2 text-sm font-semibold text-[var(--nx-base)] hover:brightness-110 transition-all"
        >
          <Plus className="h-4 w-4" />
          New Investigation
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Card label="Investigations" value={total} icon={<Crosshair className="h-4 w-4" />} />
        <Card label="Running" value={running} accent="text-amber-400" icon={<Activity className="h-4 w-4" />} />
        <Card label="Completed" value={completed} accent="text-emerald-400" icon={<CheckCircle2 className="h-4 w-4" />} />
        <Card label="Errors" value={errors} accent="text-red-400" icon={<AlertCircle className="h-4 w-4" />} />
        <Card label="Entities" value={totalEntities} accent="text-sky-400" icon={<GitBranch className="h-4 w-4" />} />
      </div>

      {/* Recent investigations */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--nx-text-tertiary)]">
            Recent Investigations
          </h2>
          <Link
            to="/investigations"
            className="text-xs font-medium text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors"
          >
            View all →
          </Link>
        </div>

        {isLoading && <LoadingState rows={3} />}
        {error && (
          <ErrorState message="Failed to load investigations." />
        )}
        {data && data.length === 0 && (
          <div className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)]">
            <EmptyState
              title="No investigations yet"
              description="Create your first investigation to start collecting OSINT data."
              action={
                <Link
                  to="/investigations/new"
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--nx-accent)] px-3 py-1.5 text-sm font-medium text-[var(--nx-base)] hover:brightness-110 transition-all"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New Investigation
                </Link>
              }
            />
          </div>
        )}

        {data && data.length > 0 && (
          <div className="overflow-hidden rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)]">
            <ul className="divide-y divide-[var(--nx-border-subtle)]">
              {data.slice(0, 5).map((inv: Investigation) => (
                <li key={inv.id}>
                  <Link
                    to={`/investigations/${inv.id}`}
                    className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-[var(--nx-surface-3)] transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium text-[var(--nx-text-primary)]">
                          {inv.name}
                        </span>
                        <span
                          className={cn(
                            "inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                            statusBadgeClass(inv.status),
                          )}
                        >
                          {inv.status}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-3 text-xs text-[var(--nx-text-muted)]">
                        <span className="font-mono text-[var(--nx-text-tertiary)]">{inv.target}</span>
                        <span className="text-[var(--nx-border-strong)]">·</span>
                        <span>{inv.entity_count} entities</span>
                        <span className="text-[var(--nx-border-strong)]">·</span>
                        <span>
                          updated {formatRelativeTime(inv.updated_at)}
                        </span>
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function Card({
  label,
  value,
  accent,
  icon,
}: {
  label: string;
  value: number;
  accent?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-4 py-3">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
        {icon && <span className={accent ?? "text-[var(--nx-text-muted)]"}>{icon}</span>}
        {label}
      </div>
      <div
        className={cn(
          "mt-1 font-mono text-2xl font-semibold tabular-nums",
          accent ?? "text-[var(--nx-text-primary)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}
