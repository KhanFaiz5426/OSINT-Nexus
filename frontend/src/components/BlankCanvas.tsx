import { Crosshair } from "lucide-react";

export function BlankCanvas() {
  return (
    <div
      data-testid="blank-canvas"
      className="cy-container relative flex h-full w-full items-center justify-center bg-[var(--nx-surface-1)] overflow-hidden select-none"
    >
      {/* Subtle, unobtrusive watermark on blank canvas */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center opacity-[0.06] dark:opacity-[0.04]">
        <Crosshair className="h-28 w-28 text-[var(--nx-text-primary)] stroke-[1]" />
      </div>
    </div>
  );
}
