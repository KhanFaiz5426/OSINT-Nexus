/**
 * UI state store for the investigation workspace.
 *
 * Holds ephemeral UI state: selected entity, panel visibility,
 * graph filter, and entity list filters. Server data is NOT stored
 * here — that lives in TanStack Query's cache.
 */

import { create } from "zustand";
import type { EntityType } from "../api/investigations";

export type EntityListSort = "confidence" | "value" | "type" | "source_count";

interface WorkspaceState {
  // Selection
  selectedEntityId: string | null;
  selectEntity: (id: string | null) => void;

  // Side panel visibility
  rightPanelOpen: boolean;
  toggleRightPanel: () => void;
  setRightPanel: (open: boolean) => void;

  // Entity list filters
  entitySearch: string;
  setEntitySearch: (q: string) => void;
  entityTypeFilter: Set<EntityType>;
  toggleEntityType: (t: EntityType) => void;
  clearEntityTypeFilter: () => void;
  minConfidence: number;
  setMinConfidence: (v: number) => void;
  sortBy: EntityListSort;
  setSortBy: (s: EntityListSort) => void;

  // Graph filter (entity types shown)
  graphTypeFilter: Set<string>;
  toggleGraphType: (t: string) => void;
  clearGraphTypeFilter: () => void;

  // Reset
  resetWorkspace: () => void;
}

const initialFilters = {
  selectedEntityId: null,
  rightPanelOpen: true,
  entitySearch: "",
  entityTypeFilter: new Set<EntityType>(),
  minConfidence: 0,
  sortBy: "confidence" as EntityListSort,
  graphTypeFilter: new Set<string>(),
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialFilters,

  selectEntity: (id) =>
    set({
      selectedEntityId: id,
      rightPanelOpen: id !== null,
    }),

  toggleRightPanel: () =>
    set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  setRightPanel: (open) => set({ rightPanelOpen: open }),

  setEntitySearch: (q) => set({ entitySearch: q }),

  toggleEntityType: (t) =>
    set((s) => {
      const next = new Set(s.entityTypeFilter);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return { entityTypeFilter: next };
    }),
  clearEntityTypeFilter: () => set({ entityTypeFilter: new Set() }),

  setMinConfidence: (v) => set({ minConfidence: v }),
  setSortBy: (s) => set({ sortBy: s }),

  toggleGraphType: (t) =>
    set((s) => {
      const next = new Set(s.graphTypeFilter);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return { graphTypeFilter: next };
    }),
  clearGraphTypeFilter: () => set({ graphTypeFilter: new Set() }),

  resetWorkspace: () =>
    set({
      ...initialFilters,
      entityTypeFilter: new Set(),
      graphTypeFilter: new Set(),
    }),
}));
