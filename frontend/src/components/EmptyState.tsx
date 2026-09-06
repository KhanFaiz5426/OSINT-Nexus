import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 text-[var(--nx-text-muted)]">
        {icon ?? <Inbox className="h-10 w-10" />}
      </div>
      <h3 className="text-sm font-medium text-[var(--nx-text-secondary)]">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[var(--nx-text-tertiary)]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
