/**
 * UI state store for the OSINT Nexus investigation workstation.
 *
 * Holds ephemeral UI state: multi-tab workspaces, active investigation,
 * selected entity, panel visibility, graph layout/fit triggers,
 * theme (dark/light), and entity list filters. Server data is stored in TanStack Query cache.
 */

import { create } from "zustand";
import type { EntityType } from "../api/investigations";

export type EntityListSort = "confidence" | "value" | "type" | "source_count";
export type GraphLayoutName = "cose" | "concentric" | "circle" | "grid";
export type BottomTabType = "timeline" | "ai" | "reports" | "settings";
export type ThemeMode = "dark" | "light";

export interface WorkspaceTab {
  id: string;
  target: string;
  name?: string;
  target_type: string;
  status?: string;
}

export function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  try {
    const saved = localStorage.getItem("nx-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {}
  return "dark";
}

export function applyTheme(theme: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "light") {
    root.classList.remove("dark");
    root.classList.add("light");
    root.setAttribute("data-theme", "light");
  } else {
    root.classList.remove("light");
    root.classList.add("dark");
    root.setAttribute("data-theme", "dark");
  }
}

interface WorkspaceState {
  // Theme
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;

  // Tabs & active workspace
  openTabs: WorkspaceTab[];
  activeTabId: string | null;
  openTab: (tab: WorkspaceTab) => void;
  closeTab: (id: string) => void;
  setActiveTab: (id: string | null) => void;
  updateTabStatus: (id: string, status: string) => void;

  // Selection
  selectedEntityId: string | null;
  selectEntity: (id: string | null) => void;

  // Panel visibility
  leftPanelOpen: boolean;
  toggleLeftPanel: () => void;
  setLeftPanel: (open: boolean) => void;

  rightPanelOpen: boolean;
  toggleRightPanel: () => void;
  setRightPanel: (open: boolean) => void;

  bottomDrawerOpen: boolean;
  toggleBottomDrawer: () => void;
  setBottomDrawer: (open: boolean) => void;
  bottomTab: BottomTabType;
  setBottomTab: (tab: BottomTabType) => void;

  // Modals
  newModalOpen: boolean;
  setNewModalOpen: (open: boolean) => void;
  openModalOpen: boolean;
  setOpenModalOpen: (open: boolean) => void;

  // Graph Layout & Controls
  graphLayout: GraphLayoutName;
  setGraphLayout: (layout: GraphLayoutName) => void;
  fitTrigger: number;
  triggerFit: () => void;

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

  // Reset current tab workspace
  resetWorkspace: () => void;
}

const initialFilters = {
  selectedEntityId: null,
  entitySearch: "",
  entityTypeFilter: new Set<EntityType>(),
  minConfidence: 0,
  sortBy: "confidence" as EntityListSort,
  graphTypeFilter: new Set<string>(),
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  // Theme
  theme: getInitialTheme(),
  setTheme: (theme) => {
    try {
      localStorage.setItem("nx-theme", theme);
    } catch {}
    applyTheme(theme);
    set({ theme });
  },
  toggleTheme: () =>
    set((s) => {
      const next: ThemeMode = s.theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("nx-theme", next);
      } catch {}
      applyTheme(next);
      return { theme: next };
    }),

  // Tabs
  openTabs: [],
  activeTabId: null,

  openTab: (tab) =>
    set((s) => {
      const exists = s.openTabs.some((t) => t.id === tab.id);
      const openTabs = exists
        ? s.openTabs.map((t) => (t.id === tab.id ? { ...t, ...tab } : t))
        : [...s.openTabs, tab];
      return {
        openTabs,
        activeTabId: tab.id,
        selectedEntityId: null,
        leftPanelOpen: true,
        rightPanelOpen: false,
      };
    }),

  closeTab: (id) =>
    set((s) => {
      const idx = s.openTabs.findIndex((t) => t.id === id);
      const remaining = s.openTabs.filter((t) => t.id !== id);
      let nextActive = s.activeTabId;

      if (s.activeTabId === id) {
        if (remaining.length === 0) {
          nextActive = null;
        } else {
          const nextIdx = Math.min(idx, remaining.length - 1);
          nextActive = remaining[nextIdx].id;
        }
      }

      return {
        openTabs: remaining,
        activeTabId: nextActive,
        selectedEntityId: null,
        leftPanelOpen: nextActive ? s.leftPanelOpen : false,
        rightPanelOpen: false,
      };
    }),

  setActiveTab: (id) =>
    set({
      activeTabId: id,
      selectedEntityId: null,
      rightPanelOpen: false,
    }),

  updateTabStatus: (id, status) =>
    set((s) => ({
      openTabs: s.openTabs.map((t) => (t.id === id ? { ...t, status } : t)),
    })),

  // Selection
  selectEntity: (id) =>
    set({
      selectedEntityId: id,
      rightPanelOpen: id !== null,
    }),

  // Panels
  leftPanelOpen: false,
  toggleLeftPanel: () => set((s) => ({ leftPanelOpen: !s.leftPanelOpen })),
  setLeftPanel: (open) => set({ leftPanelOpen: open }),

  rightPanelOpen: false,
  toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  setRightPanel: (open) => set({ rightPanelOpen: open }),

  bottomDrawerOpen: false,
  toggleBottomDrawer: () => set((s) => ({ bottomDrawerOpen: !s.bottomDrawerOpen })),
  setBottomDrawer: (open) => set({ bottomDrawerOpen: open }),
  bottomTab: "timeline",
  setBottomTab: (tab) => set({ bottomTab: tab, bottomDrawerOpen: true }),

  // Modals
  newModalOpen: false,
  setNewModalOpen: (open) => set({ newModalOpen: open }),
  openModalOpen: false,
  setOpenModalOpen: (open) => set({ openModalOpen: open }),

  // Graph Layout
  graphLayout: "cose",
  setGraphLayout: (layout) => set({ graphLayout: layout }),
  fitTrigger: 0,
  triggerFit: () => set((s) => ({ fitTrigger: s.fitTrigger + 1 })),

  // Entity list filters
  ...initialFilters,
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
