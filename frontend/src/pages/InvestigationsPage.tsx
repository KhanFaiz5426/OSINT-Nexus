import { Link } from "react-router-dom";
import { useState } from "react";
import { useInvestigations } from "../hooks/useApi";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { statusBadgeClass, formatRelativeTime } from "../lib/format";
import { cn } from "../lib/utils";
import type { InvestigationStatus } from "../api/investigations";
import { Plus, Search } from "lucide-react";

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
    <div className="mx-auto max-w-5xl py-2">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--nx-text-primary)]">
            Investigations
          </h1>
          <p className="mt-0.5 text-sm text-[var(--nx-text-muted)]">
            Manage and monitor OSINT investigations
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

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--nx-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search investigations..."
            className="block w-full rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-3)] py-1.5 pl-8 pr-3 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent-dim)] focus:outline-none transition-colors"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-md px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                statusFilter === s
                  ? "bg-[var(--nx-accent-subtle)] text-[var(--nx-accent)] border border-[var(--nx-accent)]/30"
                  : "bg-[var(--nx-surface-3)] text-[var(--nx-text-muted)] border border-[var(--nx-border)] hover:text-[var(--nx-text-secondary)]",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {isLoading && <LoadingState rows={5} />}
      {error && (
        <ErrorState message="Failed to load investigations. Is the backend running?" />
      )}
      {!isLoading && !error && filtered.length === 0 && (
        <div className="rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)]">
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
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--nx-accent)] px-3 py-1.5 text-sm font-medium text-[var(--nx-base)] hover:brightness-110 transition-all"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New Investigation
                </Link>
              )
            }
          />
        </div>
      )}

      {!isLoading && !error && filtered.length > 0 && (
        <div className="overflow-hidden rounded-md border border-[var(--nx-border)] bg-[var(--nx-surface-2)]">
          <table className="min-w-full divide-y divide-[var(--nx-border)]">
            <thead>
              <tr>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Name
                </th>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Target
                </th>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Type
                </th>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Status
                </th>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Depth
                </th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Entities
                </th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wider text-[var(--nx-text-muted)]">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--nx-border-subtle)]">
              {filtered.map((inv) => (
                <tr key={inv.id} className="hover:bg-[var(--nx-surface-3)] transition-colors">
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/investigations/${inv.id}`}
                      className="font-medium text-[var(--nx-accent)] hover:text-[var(--nx-accent)]/80 transition-colors"
                    >
                      {inv.name}
                    </Link>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span className="font-mono text-sm text-[var(--nx-text-secondary)]">{inv.target}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span className="inline-flex items-center rounded bg-[var(--nx-surface-3)] px-1.5 py-0.5 text-[10px] font-medium uppercase text-[var(--nx-text-tertiary)]">
                      {inv.target_type}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                        statusBadgeClass(inv.status),
                      )}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm capitalize text-[var(--nx-text-tertiary)]">
                    {inv.depth}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right text-sm font-mono tabular-nums text-[var(--nx-text-secondary)]">
                    {inv.entity_count}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right text-xs text-[var(--nx-text-muted)]">
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
