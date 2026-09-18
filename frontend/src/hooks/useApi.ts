/**
 * TanStack Query hooks for the OSINT Nexus API.
 *
 * Centralizes caching, invalidation, polling, and mutation logic for
 * all backend endpoints. Components consume these hooks rather than
 * calling the API client directly.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import {
  activityApi,
  aiApi,
  entitiesApi,
  graphApi,
  investigationsApi,
  reportsApi,
  type ActivityResponse,
  type AIAnalysis,
  type Entity,
  type EntityAIAnalysis,
  type GraphResponse,
  type Investigation,
  type InvestigationCreate,
  type InvestigationStartResponse,
  type InvestigationStatusDetail,
  type Observation,
  type ObservationResponse,
  type Relationship,
  type Report,
  type ReportFormat,
  type SourceAvailability,
} from "../api/investigations";

export type { ReportFormat };

// ── Investigation hooks ─────────────────────────────────────────────────────

export function useInvestigations(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): UseQueryResult<Investigation[], Error> {
  return useQuery({
    queryKey: ["investigations", params],
    queryFn: () => investigationsApi.list(params),
  });
}

export function useInvestigation(id: string | undefined): UseQueryResult<
  Investigation,
  Error
> {
  return useQuery({
    queryKey: ["investigation", id],
    queryFn: () => investigationsApi.get(id as string),
    enabled: Boolean(id),
  });
}

export function useInvestigationStatus(
  id: string | undefined,
  options?: { refetchInterval?: number },
): UseQueryResult<InvestigationStatusDetail, Error> {
  return useQuery({
    queryKey: ["investigation-status", id],
    queryFn: () => investigationsApi.status(id as string),
    enabled: Boolean(id),
    refetchInterval: options?.refetchInterval ?? false,
  });
}

export function useCreateInvestigation(): UseMutationResult<
  Investigation,
  Error,
  InvestigationCreate
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data) => investigationsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function useStopInvestigation(): UseMutationResult<
  Investigation,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => investigationsApi.stop(id),
    onMutate: async (id) => {
      // Optimistically update status to 'stopped'
      await qc.cancelQueries({ queryKey: ["investigation-status", id] });
      const previousStatus = qc.getQueryData(["investigation-status", id]);
      qc.setQueryData(["investigation-status", id], (old: any) => {
        if (!old) return old;
        return { ...old, status: "stopped" };
      });
      return { previousStatus };
    },
    onError: (_err, id, context) => {
      if (context?.previousStatus) {
        qc.setQueryData(["investigation-status", id], context.previousStatus);
      }
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
      qc.invalidateQueries({ queryKey: ["investigation", id] });
      qc.invalidateQueries({ queryKey: ["investigation-status", id] });
    },
  });
}

export function useStartInvestigation(): UseMutationResult<
  InvestigationStartResponse,
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => investigationsApi.start(id),
    onMutate: async (id) => {
      // Optimistically update status to 'running'
      await qc.cancelQueries({ queryKey: ["investigation-status", id] });
      const previousStatus = qc.getQueryData(["investigation-status", id]);
      qc.setQueryData(["investigation-status", id], (old: any) => {
        if (!old) return old;
        return { ...old, status: "running" };
      });
      return { previousStatus };
    },
    onError: (_err, id, context) => {
      if (context?.previousStatus) {
        qc.setQueryData(["investigation-status", id], context.previousStatus);
      }
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
      qc.invalidateQueries({ queryKey: ["investigation-status", id] });
    },
  });
}

export function useDeleteInvestigation(): UseMutationResult<
  { message: string },
  Error,
  string
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => investigationsApi.delete(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
      qc.removeQueries({ queryKey: ["investigation", id] });
      qc.removeQueries({ queryKey: ["investigation-status", id] });
      qc.removeQueries({ queryKey: ["graph", id] });
      qc.removeQueries({ queryKey: ["activity", id] });
      qc.removeQueries({ queryKey: ["observations", id] });
      qc.removeQueries({ queryKey: ["reports", id] });
      qc.removeQueries({ queryKey: ["ai-analysis", id] });
    },
  });
}

// ── Graph hooks ─────────────────────────────────────────────────────────────

export function useInvestigationGraph(
  investigationId: string | undefined,
  options?: { entityId?: string; depth?: number; refetchInterval?: number },
): UseQueryResult<GraphResponse, Error> {
  return useQuery({
    queryKey: [
      "graph",
      investigationId,
      options?.entityId ?? null,
      options?.depth ?? 1,
    ],
    queryFn: () =>
      graphApi.subgraph(investigationId as string, {
        entity_id: options?.entityId,
        depth: options?.depth,
      }),
    enabled: Boolean(investigationId),
    refetchInterval: options?.refetchInterval ?? false,
  });
}

// ── Entity hooks ────────────────────────────────────────────────────────────

export function useEntity(
  entityId: string | undefined,
  investigationId: string | undefined,
): UseQueryResult<Entity, Error> {
  return useQuery({
    queryKey: ["entity", entityId, investigationId],
    queryFn: () =>
      entitiesApi.get(entityId as string, investigationId as string),
    enabled: Boolean(entityId && investigationId),
  });
}

export function useEntityEvidence(
  entityId: string | undefined,
  investigationId: string | undefined,
): UseQueryResult<Observation[], Error> {
  return useQuery({
    queryKey: ["entity-evidence", entityId, investigationId],
    queryFn: () =>
      entitiesApi.evidence(entityId as string, investigationId as string),
    enabled: Boolean(entityId && investigationId),
  });
}

export function useEntityRelationships(
  entityId: string | undefined,
  investigationId: string | undefined,
): UseQueryResult<Relationship[], Error> {
  return useQuery({
    queryKey: ["entity-relationships", entityId, investigationId],
    queryFn: () =>
      entitiesApi.relationships(entityId as string, investigationId as string),
    enabled: Boolean(entityId && investigationId),
  });
}

export function useEntityAIAnalysis(
  entityId: string | undefined,
  investigationId: string | undefined,
): UseQueryResult<EntityAIAnalysis, Error> {
  return useQuery({
    queryKey: ["entity-ai-analysis", entityId, investigationId],
    queryFn: () =>
      entitiesApi.aiAnalysis(entityId as string, investigationId as string),
    enabled: Boolean(entityId && investigationId),
    staleTime: 60_000,
  });
}

// ── Activity / Timeline hooks ───────────────────────────────────────────────

export function useActivity(
  investigationId: string | undefined,
  params?: { limit?: number; offset?: number },
): UseQueryResult<ActivityResponse, Error> {
  return useQuery({
    queryKey: ["activity", investigationId, params],
    queryFn: () =>
      activityApi.list(investigationId as string, params),
    enabled: Boolean(investigationId),
    refetchInterval: 5_000,
  });
}

export function useObservations(
  investigationId: string | undefined,
  params?: { limit?: number; offset?: number },
): UseQueryResult<ObservationResponse, Error> {
  return useQuery({
    queryKey: ["observations", investigationId, params],
    queryFn: () =>
      activityApi.observations(investigationId as string, params),
    enabled: Boolean(investigationId),
  });
}

// ── AI hooks ─────────────────────────────────────────────────────────────────

export function useAIAnalysis(
  investigationId: string | undefined,
  options?: { refetchInterval?: number },
): UseQueryResult<AIAnalysis, Error> {
  return useQuery({
    queryKey: ["ai-analysis", investigationId],
    queryFn: () => aiApi.analysis(investigationId as string),
    enabled: Boolean(investigationId),
    refetchInterval: options?.refetchInterval ?? false,
  });
}

// ── Report hooks ────────────────────────────────────────────────────────────

export function useReports(
  investigationId: string | undefined,
): UseQueryResult<Report[], Error> {
  return useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => reportsApi.list(investigationId as string),
    enabled: Boolean(investigationId),
  });
}

export function useGenerateReport(): UseMutationResult<
  Report,
  Error,
  { investigationId: string; format: ReportFormat }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ investigationId, format }) =>
      reportsApi.generate(investigationId, { format }),
    onSuccess: (_data, { investigationId }) => {
      qc.invalidateQueries({ queryKey: ["reports", investigationId] });
    },
  });
}

// ── Source Availability hooks ───────────────────────────────────────────────

export function useSourceAvailability(
  entityId: string | undefined,
  investigationId: string | undefined,
): UseQueryResult<SourceAvailability, Error> {
  return useQuery({
    queryKey: ["source-availability", entityId, investigationId],
    queryFn: () =>
      entitiesApi.sourceAvailability(entityId as string, investigationId as string),
    enabled: Boolean(entityId && investigationId),
    staleTime: 30 * 60 * 1000, // 30 minutes — availability doesn't change rapidly
  });
}

// ── SSE Hook for real-time investigation updates ───────────────────────────

const sseConnections = new Map<string, EventSource>();

/**
 * Subscribe to SSE events for a running investigation.
 * Invalidates relevant TanStack Query caches on events.
 * Reuses existing EventSource connections to prevent duplicates.
 * Cleans up on unmount or when investigation reaches terminal state.
 */
export function useInvestigationSSE(investigationId: string | undefined) {
  const queryClient = useQueryClient();
  const terminalStates = useRef(new Set<string>());

  useEffect(() => {
    if (!investigationId) return;
    const invId = investigationId;

    // Don't reconnect if we've already seen a terminal event for this investigation
    if (terminalStates.current.has(invId)) return;

    // Reuse existing connection
    if (sseConnections.has(invId)) return;

    const eventSource = new EventSource(
      `/api/v1/investigations/${invId}/events`,
    );
    sseConnections.set(invId, eventSource);

    const invalidate = (...queryKeys: Array<string | undefined>) => {
      for (const key of queryKeys) {
        if (key) {
          queryClient.invalidateQueries({ queryKey: [key, invId] });
        }
      }
      // Also invalidate entity-list queries (they use investigationId in the key)
      queryClient.invalidateQueries({ queryKey: ["entity-list", invId] });
    };

    const handleStarted = () => {
      invalidate("investigation-status", "investigation", "investigations");
    };

    const handleRoundCompleted = () => {
      invalidate(
        "investigation-status",
        "graph",
        "activity",
        "entity-list",
        "investigations"
      );
    };

    const handleCompleted = () => {
      terminalStates.current.add(invId);
      invalidate(
        "investigation-status",
        "investigation",
        "graph",
        "activity",
        "entity-list",
        "ai-analysis",
        "investigations"
      );
      cleanup();
    };

    const handleError = () => {
      terminalStates.current.add(invId);
      invalidate("investigation-status", "investigation", "investigations");
      cleanup();
    };

    const handleConnected = () => {
      // SSE connection established
    };

    const handleHeartbeat = () => {
      // Keep-alive, no action needed
    };

    eventSource.addEventListener("investigation_started", handleStarted);
    eventSource.addEventListener("pivot_round_completed", handleRoundCompleted);
    eventSource.addEventListener("investigation_completed", handleCompleted);
    eventSource.addEventListener("investigation_error", handleError);
    eventSource.addEventListener("connected", handleConnected);
    eventSource.addEventListener("heartbeat", handleHeartbeat);

    // Fallback: also handle generic "message" events
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === "completed" || data.status === "error") {
          terminalStates.current.add(invId);
          invalidate(
            "investigation-status",
            "investigation",
            "graph",
            "activity",
            "entity-list",
            "investigations"
          );
          cleanup();
        }
      } catch {
        // Ignore parse errors for heartbeat/non-JSON messages
      }
    };

    eventSource.onerror = () => {
      // SSE connection error — will auto-reconnect per spec
      // If consistently failing, the polling fallback in useInvestigationStatus handles it
    };

    function cleanup() {
      eventSource.close();
      sseConnections.delete(invId);
    }

    return cleanup;
  }, [investigationId, queryClient]);
}
