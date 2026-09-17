import { useWorkspaceStore } from "../store/workspace";
import { AlertCircle, FolderOpen } from "lucide-react";
import { useWorkspaceActions } from "../hooks/useWorkspaceActions";

export function WorkspaceModals() {
  const blockerOpen = useWorkspaceStore((s) => s.openWorkspaceBlockerOpen);
  const setBlockerOpen = useWorkspaceStore((s) => s.setOpenWorkspaceBlockerOpen);
  
  const confirmOpen = useWorkspaceStore((s) => s.openWorkspaceConfirmOpen);
  const setConfirmOpen = useWorkspaceStore((s) => s.setOpenWorkspaceConfirmOpen);
  
  const { proceedWithOpenWorkspace } = useWorkspaceActions();

  return (
    <>
      {/* Blocker Modal */}
      {blockerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-xl border border-[var(--nx-border)] bg-[var(--nx-surface-1)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6">
              <div className="flex items-center gap-3 text-amber-500 mb-4">
                <AlertCircle className="h-6 w-6" />
                <h2 className="text-lg font-semibold text-[var(--nx-text-primary)]">Investigation is still running</h2>
              </div>
              <p className="text-sm text-[var(--nx-text-secondary)] leading-relaxed">
                An investigation is currently active in this workspace. You must wait for it to finish or stop it before opening another workspace.
              </p>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 bg-[var(--nx-surface-2)] border-t border-[var(--nx-border)]">
              <button
                type="button"
                onClick={() => setBlockerOpen(false)}
                className="rounded-md px-4 py-2 text-sm font-medium text-[var(--nx-text-primary)] bg-[var(--nx-surface-3)] hover:bg-[var(--nx-surface-4)] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-xl border border-[var(--nx-border)] bg-[var(--nx-surface-1)] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6">
              <div className="flex items-center gap-3 text-sky-500 mb-4">
                <FolderOpen className="h-6 w-6" />
                <h2 className="text-lg font-semibold text-[var(--nx-text-primary)]">Open another workspace?</h2>
              </div>
              <p className="text-sm text-[var(--nx-text-secondary)] leading-relaxed">
                Your current workspace will be safely closed before opening the selected workspace.
              </p>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 bg-[var(--nx-surface-2)] border-t border-[var(--nx-border)]">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="rounded-md px-4 py-2 text-sm font-medium text-[var(--nx-text-secondary)] hover:bg-[var(--nx-surface-3)] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => proceedWithOpenWorkspace()}
                className="rounded-md px-4 py-2 text-sm font-medium text-[var(--nx-base)] bg-[var(--nx-accent)] hover:brightness-110 active:scale-95 transition-all"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
