import { FolderOpen, Plus } from "lucide-react";
import { useWorkspaceActions } from "../hooks/useWorkspaceActions";
import { Spinner } from "./LoadingState";

export function LandingCanvas() {
  const { handleNewWorkspace, handleOpenWorkspace, isWorkspaceBusy, workspaceError } = useWorkspaceActions();

  return (
    <div className="flex h-full w-full items-center justify-center bg-[var(--nx-base)] overflow-hidden select-none">
      <div className="flex flex-col items-center animate-in fade-in zoom-in duration-300">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--nx-surface-1)] shadow-sm border border-[var(--nx-border)]">
          <img src="/osint-nexus-logo.svg" alt="OSINT Nexus" className="h-10 w-10 opacity-90" />
        </div>
        
        <h1 className="mb-2 text-xl font-medium tracking-tight text-[var(--nx-text-primary)]">
          OSINT Nexus
        </h1>
        <p className="mb-8 text-sm text-[var(--nx-text-muted)]">
          Create or Open a Workspace to begin
        </p>

        {workspaceError && (
          <div className="mb-6 rounded-md bg-red-500/10 border border-red-500/20 px-4 py-2 text-xs text-red-400 max-w-sm text-center">
            {workspaceError}
          </div>
        )}

        <div className="flex flex-col gap-3 w-64">
          <button
            onClick={handleNewWorkspace}
            disabled={isWorkspaceBusy}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-[var(--nx-accent)] px-4 py-2.5 text-sm font-medium text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 shadow-sm disabled:opacity-50 disabled:pointer-events-none"
          >
            {isWorkspaceBusy ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" strokeWidth={2.5} />}
            <span>Create Workspace</span>
          </button>
          
          <button
            onClick={handleOpenWorkspace}
            disabled={isWorkspaceBusy}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-[var(--nx-border-strong)] bg-[var(--nx-surface-2)] px-4 py-2.5 text-sm font-medium text-[var(--nx-text-secondary)] transition-all hover:bg-[var(--nx-surface-3)] hover:text-[var(--nx-text-primary)] active:scale-95 shadow-sm disabled:opacity-50 disabled:pointer-events-none"
          >
            {isWorkspaceBusy ? <Spinner className="h-4 w-4" /> : <FolderOpen className="h-4 w-4" />}
            <span>Open Workspace</span>
          </button>
        </div>
      </div>
    </div>
  );
}
