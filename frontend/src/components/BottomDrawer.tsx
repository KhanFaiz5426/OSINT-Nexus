import { useCallback, useRef } from "react";
import {
  Activity,
  Brain,
  ChevronDown,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { useWorkspaceStore } from "../store/workspace";
import { TimelinePanel } from "./TimelinePanel";
import { EntityIntelligencePanel } from "./EntityIntelligencePanel";
import { cn } from "../lib/utils";

interface BottomDrawerProps {
  investigationId: string;
}

export function BottomDrawer({ investigationId }: BottomDrawerProps) {
  const bottomDrawerOpen = useWorkspaceStore((s) => s.bottomDrawerOpen);
  const toggleBottomDrawer = useWorkspaceStore((s) => s.toggleBottomDrawer);
  const bottomTab = useWorkspaceStore((s) => s.bottomTab);
  const setBottomTab = useWorkspaceStore((s) => s.setBottomTab);
  const bottomDrawerHeight = useWorkspaceStore((s) => s.bottomDrawerHeight);
  const setBottomDrawerHeight = useWorkspaceStore(
    (s) => s.setBottomDrawerHeight,
  );
  const bottomDrawerMaximized = useWorkspaceStore(
    (s) => s.bottomDrawerMaximized,
  );
  const toggleBottomDrawerMaximized = useWorkspaceStore(
    (s) => s.toggleBottomDrawerMaximized,
  );
  const selectedEntityId = useWorkspaceStore((s) => s.selectedEntityId);

  const resizeRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const startYRef = useRef(0);
  const startHeightRef = useRef(0);

  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      draggingRef.current = true;
      startYRef.current = e.clientY;
      startHeightRef.current = bottomDrawerHeight;

      const handleMouseMove = (ev: MouseEvent) => {
        if (!draggingRef.current) return;
        const delta = startYRef.current - ev.clientY;
        const newHeight = startHeightRef.current + delta;
        setBottomDrawerHeight(newHeight);
      };

      const handleMouseUp = () => {
        draggingRef.current = false;
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "ns-resize";
      document.body.style.userSelect = "none";
    },
    [bottomDrawerHeight, setBottomDrawerHeight],
  );

  if (!bottomDrawerOpen) return null;

  const effectiveHeight = bottomDrawerMaximized ? "100%" : `${bottomDrawerHeight}px`;

  return (
    <div
      className="flex shrink-0 flex-col border-t border-[var(--nx-border)] bg-[var(--nx-surface-1)] z-20"
      style={{
        height: effectiveHeight,
        ...(bottomDrawerMaximized
          ? { position: "absolute", inset: 0, zIndex: 30 }
          : {}),
      }}
    >
      {/* Resize handle */}
      {!bottomDrawerMaximized && (
        <div
          ref={resizeRef}
          onMouseDown={handleResizeStart}
          className="h-1 w-full cursor-ns-resize bg-transparent hover:bg-[var(--nx-accent)]/30 transition-colors group flex items-center justify-center shrink-0"
        >
          <div className="h-0.5 w-8 rounded-full bg-[var(--nx-border-strong)] group-hover:bg-[var(--nx-accent)] transition-colors" />
        </div>
      )}

      {/* Drawer Tab Header */}
      <div className="flex h-8 shrink-0 items-center justify-between border-b border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2 select-none">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setBottomTab("entity-intel")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "entity-intel"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <Brain className="h-3.5 w-3.5" />
            <span>Entity Intelligence</span>
            {selectedEntityId && bottomTab === "entity-intel" && (
              <span className="ml-1 h-1.5 w-1.5 rounded-full bg-[var(--nx-accent)] animate-pulse" />
            )}
          </button>

          <button
            onClick={() => setBottomTab("timeline")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded transition-colors",
              bottomTab === "timeline"
                ? "bg-[var(--nx-surface-3)] text-[var(--nx-accent)]"
                : "text-[var(--nx-text-tertiary)] hover:bg-[var(--nx-surface-3)]/50 hover:text-[var(--nx-text-secondary)]",
            )}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Activity & Observations</span>
          </button>
        </div>

        <div className="flex items-center gap-0.5">
          {/* Maximize / Restore button */}
          <button
            onClick={toggleBottomDrawerMaximized}
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
            title={bottomDrawerMaximized ? "Restore" : "Maximize"}
          >
            {bottomDrawerMaximized ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>

          {/* Collapse button */}
          <button
            onClick={() => {
              if (bottomDrawerMaximized) toggleBottomDrawerMaximized();
              toggleBottomDrawer();
            }}
            className="rounded p-1 text-[var(--nx-text-muted)] hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] transition-colors"
            title="Minimize drawer"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Drawer Body */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {bottomTab === "entity-intel" && (
          <EntityIntelligencePanel investigationId={investigationId} />
        )}
        {bottomTab === "timeline" && (
          <TimelinePanel investigationId={investigationId} />
        )}
      </div>
    </div>
  );
}
