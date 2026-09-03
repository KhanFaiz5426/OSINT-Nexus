import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  label?: string;
  rows?: number;
}

export function LoadingState({ label = "Loading...", rows = 3 }: LoadingStateProps) {
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-10 animate-pulse rounded-md bg-gray-100"
          style={{ width: `${85 - i * 6}%` }}
        />
      ))}
    </div>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} />;
}
