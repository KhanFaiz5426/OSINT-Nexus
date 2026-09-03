import { Link } from "react-router-dom";
import { useState } from "react";
import { useInvestigations } from "../hooks/useApi";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { statusBadgeClass, formatRelativeTime } from "../lib/format";
import { cn } from "../lib/utils";
import type { InvestigationStatus } from "../api/investigations";

const STATUSES: (InvestigationStatus | "all")[] = [
  "all",
  "created",
  "running",
  "completed",
  "stopped",
  "error",
];

export function InvestigationsPage() {
  const [statusFilter, setStatusFilter] = useState<InvestigationStatus | "all">(
    "all",
  );
  const [search, setSearch] = useState("");
  const params =
    statusFilter === "all" ? undefined : { status: statusFilter, limit: 50 };
  const { data, isLoading, error } = useInvestigations(params);

  const filtered = (data ?? []).filter((inv) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      inv.name.toLowerCase().includes(q) ||
      inv.target.toLowerCase().includes(q) ||
      inv.target_type.toLowerCase().includes(q)
    );
  });

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            Investigations
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage and monitor OSINT investigations
          </p>
        </div>
        <Link
          to="/investigations/new"
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          New Investigation
        </Link>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search investigations..."
          className="block flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:max-w-xs"
        />
        <div className="flex flex-wrap gap-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide transition-colors",
                statusFilter === s
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <LoadingState rows={5} />}
      {error && (
        <ErrorState message="Failed to load investigations. Is the backend running?" />
      )}
      {!isLoading && !error && filtered.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <EmptyState
            title={search || statusFilter !== "all" ? "No matches" : "No investigations yet"}
            description={
              search || statusFilter !== "all"
                ? "Try adjusting your filters."
                : "Create your first investigation to get started."
            }
            action={
              !search &&
              statusFilter === "all" && (
                <Link
                  to="/investigations/new"
                  className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
                >
                  New Investigation
                </Link>
              )
            }
          />
        </div>
      )}

      {!isLoading && !error && filtered.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Target
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Depth
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Entities
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {filtered.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      to={`/investigations/${inv.id}`}
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {inv.name}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="font-mono text-sm">{inv.target}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                      {inv.target_type}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
                        statusBadgeClass(inv.status),
                      )}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-sm capitalize text-gray-700">
                    {inv.depth}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-sm tabular-nums text-gray-700">
                    {inv.entity_count}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-xs text-gray-500">
                    {formatRelativeTime(inv.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
