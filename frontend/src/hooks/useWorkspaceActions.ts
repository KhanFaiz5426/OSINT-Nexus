import { useState, useEffect, useCallback } from "react";
import { useWorkspaceStore } from "../store/workspace";
import {
  useOpenWorkspace,
  useCreateWorkspace,
  useSaveWorkspaceAs,
} from "./useWorkspaceApi";
import { investigationsApi } from "../api/investigations";

// ── PyWebview type guard ────────────────────────────────────────────────────

interface PyWebviewApi {
  open_file_dialog: () => Promise<string | null>;
  save_file_dialog: () => Promise<string | null>;
  select_folder_dialog: () => Promise<string | null>;
  open_external: (url: string) => Promise<void>;
}

export function getPyWebviewApi(): PyWebviewApi | null {
  try {
    const w = window as unknown as { pywebview?: { api?: PyWebviewApi } };
    return w.pywebview?.api ?? null;
  } catch {
    return null;
  }
}

// ── Shared Workspace Actions ────────────────────────────────────────────────

export function useWorkspaceActions() {
  const setNewWorkspaceModalOpen = useWorkspaceStore((s) => s.setNewWorkspaceModalOpen);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);
  
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const resetWorkspaceUiState = useWorkspaceStore((s) => s.resetWorkspaceUiState);
  
  const openWorkspace = useOpenWorkspace();
  const createWorkspace = useCreateWorkspace();
  const saveWorkspaceAs = useSaveWorkspaceAs();
  
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  
  const isWorkspaceBusy =
    openWorkspace.isPending || createWorkspace.isPending || saveWorkspaceAs.isPending;

  // Clear workspace error after 5 seconds
  useEffect(() => {
    if (!workspaceError) return;
    const t = setTimeout(() => setWorkspaceError(null), 5000);
    return () => clearTimeout(t);
  }, [workspaceError]);

  const setOpenWorkspaceBlockerOpen = useWorkspaceStore((s) => s.setOpenWorkspaceBlockerOpen);
  const setOpenWorkspaceConfirmOpen = useWorkspaceStore((s) => s.setOpenWorkspaceConfirmOpen);

  const proceedWithOpenWorkspace = useCallback(async () => {
    const api = getPyWebviewApi();
    if (!api) {
      setWorkspaceError("Native file dialogs are only available in the desktop app.");
      return;
    }
    try {
      const path = await api.open_file_dialog();
      if (!path) return; // cancelled
      await openWorkspace.mutateAsync(path);
      setWorkspaceError(null);
      resetWorkspaceUiState();
      
      // Auto-open investigation logic
      const investigations = await investigationsApi.list();
      if (investigations.length === 1) {
        const inv = investigations[0];
        openTab({
          id: inv.id,
          target: inv.target,
          name: inv.name,
          target_type: inv.target_type,
          status: inv.status,
        });
      } else {
        setOpenModalOpen(true);
      }
      setOpenWorkspaceConfirmOpen(false);
    } catch (err: unknown) {
      setWorkspaceError(err instanceof Error ? err.message : "Failed to open workspace.");
    }
  }, [openWorkspace, openTab, setOpenModalOpen, resetWorkspaceUiState, setOpenWorkspaceConfirmOpen]);

  const handleOpenWorkspace = useCallback(async () => {
    try {
      // Import workspaceApi directly to check current status
      const { workspaceApi } = await import("../api/workspace");
      const { active_workspace } = await workspaceApi.status();
      
      if (!active_workspace) {
        await proceedWithOpenWorkspace();
        return;
      }

      const investigations = await investigationsApi.list();
      const hasRunning = investigations.some((inv) => inv.status === "running");

      if (hasRunning) {
        setOpenWorkspaceBlockerOpen(true);
      } else {
        setOpenWorkspaceConfirmOpen(true);
      }
    } catch (err: unknown) {
      setWorkspaceError(err instanceof Error ? err.message : "Failed to check workspace state.");
    }
  }, [proceedWithOpenWorkspace, setOpenWorkspaceBlockerOpen, setOpenWorkspaceConfirmOpen]);

  const handleNewWorkspace = useCallback(() => {
    setNewWorkspaceModalOpen(true);
  }, [setNewWorkspaceModalOpen]);

  const handleNewInvestigation = useCallback(async () => {
    setNewModalOpen(true);
  }, [setNewModalOpen]);

  const handleSaveAs = useCallback(async () => {
    const api = getPyWebviewApi();
    if (!api) {
      setWorkspaceError("Native file dialogs are only available in the desktop app.");
      return;
    }
    try {
      const path = await api.save_file_dialog();
      if (!path) return; // cancelled
      await saveWorkspaceAs.mutateAsync(path);
      setWorkspaceError(null);
    } catch (err: unknown) {
      setWorkspaceError(err instanceof Error ? err.message : "Failed to save workspace.");
    }
  }, [saveWorkspaceAs]);

  return {
    handleOpenWorkspace,
    proceedWithOpenWorkspace,
    handleNewWorkspace,
    handleNewInvestigation,
    handleSaveAs,
    isWorkspaceBusy,
    workspaceError,
  };
}
