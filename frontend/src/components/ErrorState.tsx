import { AlertTriangle } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="rounded-md border border-red-500/25 bg-red-500/10 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 shrink-0 text-red-400" />
        <div className="flex-1">
          <h3 className="text-sm font-medium text-red-300">{title}</h3>
          <p className="mt-1 text-sm text-red-400/80">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 inline-flex items-center rounded-md border border-red-500/30 bg-red-500/10 px-3 py-1 text-sm font-medium text-red-300 hover:bg-red-500/20 transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
