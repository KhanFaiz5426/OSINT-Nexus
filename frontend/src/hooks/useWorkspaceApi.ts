/**
 * TanStack Query hooks for workspace management.
 *
 * Provides query/mutation wrappers around the workspace API client.
 * Follows the same patterns as useApi.ts.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { workspaceApi, type WorkspaceStatus } from "../api/workspace";

// ── Query keys ──────────────────────────────────────────────────────────────

export const WORKSPACE_KEY = ["workspace-status"] as const;

// ── Queries ─────────────────────────────────────────────────────────────────

/**
 * Fetch the currently active workspace path.
 * Polls every 30s to stay in sync with backend state changes.
 */
export function useWorkspaceStatus(): UseQueryResult<WorkspaceStatus, Error> {
  return useQuery({
    queryKey: WORKSPACE_KEY,
    queryFn: () => workspaceApi.status(),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

// ── Mutations ───────────────────────────────────────────────────────────────

/**
 * Open an existing .osint workspace file.
 * Invalidates workspace status and all investigation-related caches on success.
 */
export function useOpenWorkspace(): UseMutationResult<
  WorkspaceStatus,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => workspaceApi.open(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WORKSPACE_KEY });
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

/**
 * Create a new .osint workspace at the given path.
 * Invalidates workspace status and all investigation-related caches on success.
 */
export function useCreateWorkspace(): UseMutationResult<
  WorkspaceStatus,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => workspaceApi.create(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WORKSPACE_KEY });
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

/**
 * Save a snapshot of the active workspace to a new file.
 * Invalidates workspace status on success.
 */
export function useSaveWorkspaceAs(): UseMutationResult<
  WorkspaceStatus,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => workspaceApi.saveAs(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: WORKSPACE_KEY });
    },
  });
}
