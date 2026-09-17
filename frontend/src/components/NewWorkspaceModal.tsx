import { useState, useEffect } from "react";
import { useWorkspaceStore } from "../store/workspace";
import { FolderPlus, ArrowRight, ArrowLeft } from "lucide-react";
import { getPyWebviewApi } from "../hooks/useWorkspaceActions";
import { useCreateWorkspace } from "../hooks/useWorkspaceApi";
import { Spinner } from "./LoadingState";

export function NewWorkspaceModal() {
  const open = useWorkspaceStore((s) => s.newWorkspaceModalOpen);
  const setOpen = useWorkspaceStore((s) => s.setNewWorkspaceModalOpen);
  const resetWorkspaceUiState = useWorkspaceStore((s) => s.resetWorkspaceUiState);
  
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState("");
  const [folderPath, setFolderPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateWorkspace();

  // Reset state when opening/closing
  useEffect(() => {
    if (open) {
      setStep(1);
      setName("");
      setFolderPath(null);
      setError(null);
    }
  }, [open]);

  // Handle escape key
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, setOpen]);

  if (!open) return null;

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) setStep(2);
  };

  const handleSelectFolder = async () => {
    const api = getPyWebviewApi();
    if (!api) {
      setError("Native file dialogs are only available in the desktop app.");
      return;
    }
    try {
      const path = await api.select_folder_dialog();
      if (path) setFolderPath(path);
    } catch (err: any) {
      setError(err.message || "Failed to select folder.");
    }
  };

  const handleCreate = async () => {
    if (!name.trim() || !folderPath) return;
    setError(null);

    try {
      const safeName = name.trim().replace(/[^a-zA-Z0-9_-]/g, "_");
      const fullPath = `${folderPath}\\${safeName}.osint`;

      await createMutation.mutateAsync(fullPath);
      resetWorkspaceUiState();
      setOpen(false);
    } catch (err: any) {
      setError(err.message || "Failed to create workspace.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-xl border border-[var(--nx-border)] bg-[var(--nx-surface-1)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--nx-border)] px-5 py-3.5 bg-[var(--nx-surface-2)]">
          <div className="flex items-center gap-2 text-[var(--nx-text-primary)]">
            <FolderPlus className="h-5 w-5 text-sky-500" />
            <h2 className="text-sm font-semibold tracking-wide uppercase">New Workspace</h2>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="text-[var(--nx-text-muted)] hover:text-[var(--nx-text-secondary)] transition-colors"
          >
            ✕
          </button>
        </div>
        
        {error && (
          <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Step 1 */}
        {step === 1 && (
          <form onSubmit={handleNext} className="p-4 space-y-3">
            <div>
              <label htmlFor="ws-name" className="block text-sm font-medium text-[var(--nx-text-secondary)] mb-1">
                Workspace name
              </label>
              <input
                id="ws-name"
                autoFocus
                type="text"
                placeholder="e.g. Project-Alpha"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-2.5 py-1.5 text-sm text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:border-[var(--nx-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--nx-accent)]"
              />
              <p className="mt-1.5 text-xs text-[var(--nx-text-muted)]">
                You will be prompted to choose a folder location on the next step.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--nx-border)]">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded px-4 py-1.5 text-sm font-medium text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!name.trim()}
                className="inline-flex items-center gap-2 rounded bg-[var(--nx-accent)] px-4 py-1.5 text-sm font-medium text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 disabled:opacity-50"
              >
                <span>Next</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div className="p-4 space-y-4">
            <p className="text-sm text-[var(--nx-text-secondary)]">
              Choose where to save this workspace.
            </p>
            
            <div>
              <label className="block text-xs font-medium text-[var(--nx-text-secondary)] mb-1">
                Location:
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={folderPath || ""}
                  placeholder="Select a folder..."
                  className="flex-1 rounded border border-[var(--nx-border)] bg-[var(--nx-surface-2)] px-2.5 py-1.5 text-xs font-mono text-[var(--nx-text-primary)] placeholder:text-[var(--nx-text-muted)] focus:outline-none cursor-pointer hover:bg-[var(--nx-surface-3)] transition-colors"
                  onClick={handleSelectFolder}
                />
                <button
                  type="button"
                  onClick={handleSelectFolder}
                  className="rounded border border-[var(--nx-border)] bg-[var(--nx-surface-3)] px-3 py-1.5 text-xs font-medium text-[var(--nx-text-primary)] hover:bg-[var(--nx-surface-4)] transition-colors"
                >
                  Browse...
                </button>
              </div>

              {folderPath && name.trim() && (
                <p className="mt-2 text-xs text-[var(--nx-text-muted)] leading-tight">
                  The workspace will be saved as:<br/>
                  <span className="font-mono text-[var(--nx-text-secondary)]">
                    {folderPath}\{name.trim().replace(/[^a-zA-Z0-9_-]/g, "_")}.osint
                  </span>
                </p>
              )}
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-[var(--nx-border)] mt-4">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-2 rounded px-4 py-1.5 text-sm font-medium text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Back</span>
              </button>
              
              <button
                type="button"
                onClick={handleCreate}
                disabled={!folderPath || createMutation.isPending}
                className="inline-flex items-center gap-2 rounded bg-[var(--nx-accent)] px-4 py-1.5 text-sm font-medium text-[var(--nx-base)] transition-all hover:brightness-110 active:scale-95 disabled:opacity-50"
              >
                {createMutation.isPending && <Spinner className="h-3.5 w-3.5" />}
                <span>Create Workspace</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
