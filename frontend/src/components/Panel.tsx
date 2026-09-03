import type { ReactNode } from "react";
import { cn } from "../lib/utils";

interface PanelProps {
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  noPadding?: boolean;
  children: ReactNode;
}

export function Panel({
  title,
  actions,
  className,
  bodyClassName,
  noPadding,
  children,
}: PanelProps) {
  return (
    <section
      className={cn(
        "flex flex-col rounded-lg border border-gray-200 bg-white shadow-sm",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-gray-200 px-4 py-2.5">
          {title && (
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
              {title}
            </h2>
          )}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div
        className={cn(
          "min-h-0 flex-1 overflow-auto",
          noPadding ? "" : "p-4",
          bodyClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}
