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
import {
  activityApi,
  aiApi,
  entitiesApi,
  graphApi,
  investigationsApi,
  type ActivityResponse,
  type AIAnalysis,
  type Entity,
  type GraphResponse,
  type Investigation,
  type InvestigationCreate,
  type InvestigationStartResponse,
  type InvestigationStatusDetail,
  type Observation,
  type ObservationResponse,
  type Relationship,
} from "../api/investigations";

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
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
      qc.invalidateQueries({ queryKey: ["investigation", data.id] });
      qc.invalidateQueries({ queryKey: ["investigation-status", data.id] });
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
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["investigation", id] });
      qc.invalidateQueries({ queryKey: ["investigation-status", id] });
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
