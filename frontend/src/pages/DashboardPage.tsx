import { Link } from "react-router-dom";
import { useInvestigations } from "../hooks/useApi";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { statusBadgeClass, formatRelativeTime } from "../lib/format";
import { cn } from "../lib/utils";
import type { Investigation } from "../api/investigations";

export function DashboardPage() {
  const { data, isLoading, error } = useInvestigations({ limit: 5 });

  const total = data?.length ?? 0;
  const running = data?.filter((i) => i.status === "running").length ?? 0;
  const completed = data?.filter((i) => i.status === "completed").length ?? 0;
  const errors = data?.filter((i) => i.status === "error").length ?? 0;
  const totalEntities = data?.reduce((s, i) => s + i.entity_count, 0) ?? 0;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          AI-assisted OSINT investigation workstation
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Card label="Total Investigations" value={total} />
        <Card label="Running" value={running} accent="text-yellow-700" />
        <Card label="Completed" value={completed} accent="text-green-700" />
        <Card label="Errors" value={errors} accent="text-red-700" />
        <Card
          label="Total Entities"
          value={totalEntities}
          accent="text-blue-700"
        />
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
            Recent Investigations
          </h2>
          <Link
            to="/investigations"
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            View all →
          </Link>
        </div>

        {isLoading && <LoadingState rows={3} />}
        {error && (
          <ErrorState message="Failed to load investigations." />
        )}
        {data && data.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white">
            <EmptyState
              title="No investigations yet"
              description="Create your first investigation to start collecting OSINT data."
              action={
                <Link
                  to="/investigations/new"
                  className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
                >
                  New Investigation
                </Link>
              }
            />
          </div>
        )}

        {data && data.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <ul className="divide-y divide-gray-100">
              {data.slice(0, 5).map((inv: Investigation) => (
                <li key={inv.id}>
                  <Link
                    to={`/investigations/${inv.id}`}
                    className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-gray-50"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium text-gray-900">
                          {inv.name}
                        </span>
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
                            statusBadgeClass(inv.status),
                          )}
                        >
                          {inv.status}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                        <span className="font-mono">{inv.target}</span>
                        <span>·</span>
                        <span>{inv.entity_count} entities</span>
                        <span>·</span>
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
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 font-mono text-2xl font-semibold tabular-nums",
          accent ?? "text-gray-900",
        )}
      >
        {value}
      </div>
    </div>
  );
}
