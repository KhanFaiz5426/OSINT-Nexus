import { useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useWorkspaceStore, applyTheme } from "../store/workspace";
import { useInvestigation } from "../hooks/useApi";
import { WorkstationHeader } from "../components/WorkstationHeader";
import { InvestigationTabBar } from "../components/InvestigationTabBar";
import { WorkstationStatusBar } from "../components/WorkstationStatusBar";
import { BlankCanvas } from "../components/BlankCanvas";
import { GraphView } from "../components/GraphView";
import { GraphLegend } from "../components/GraphLegend";
import { EntityListPanel } from "../components/EntityListPanel";
import { BottomDrawer } from "../components/BottomDrawer";
import { NewInvestigationModal } from "../components/NewInvestigationModal";
import { OpenInvestigationModal } from "../components/OpenInvestigationModal";

export function WorkstationPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const theme = useWorkspaceStore((s) => s.theme);
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const setActiveTab = useWorkspaceStore((s) => s.setActiveTab);
  const setNewModalOpen = useWorkspaceStore((s) => s.setNewModalOpen);
  const setOpenModalOpen = useWorkspaceStore((s) => s.setOpenModalOpen);

  const leftPanelOpen = useWorkspaceStore((s) => s.leftPanelOpen);
  const selectEntity = useWorkspaceStore((s) => s.selectEntity);
  const triggerFit = useWorkspaceStore((s) => s.triggerFit);

  // Sync theme with DOM
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // If URL has an ID that is not yet in openTabs, fetch it and open tab
  const urlInvestigation = useInvestigation(id ?? "");

  useEffect(() => {
    if (id && urlInvestigation.data) {
      const inv = urlInvestigation.data;
      openTab({
        id: inv.id,
        target: inv.target,
        name: inv.name,
        target_type: inv.target_type,
        status: inv.status,
      });
      setActiveTab(inv.id);
    }
  }, [id, urlInvestigation.data, openTab, setActiveTab]);

  // If URL is /investigations/new, pop new modal
  useEffect(() => {
    if (location.pathname === "/investigations/new") {
      setNewModalOpen(true);
    } else if (location.pathname === "/investigations") {
      setOpenModalOpen(true);
    }
  }, [location.pathname, setNewModalOpen, setOpenModalOpen]);

  // Keep URL in sync with activeTabId
  useEffect(() => {
    if (activeTabId && activeTabId !== id) {
      navigate(`/investigations/${activeTabId}`, { replace: true });
    } else if (!activeTabId && id) {
      navigate("/", { replace: true });
    }
  }, [activeTabId, id, navigate]);

  // Global keyboard shortcuts for workstation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is currently typing in an input/textarea
      const target = e.target as HTMLElement | null;
      const isInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        setNewModalOpen(true);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o") {
        e.preventDefault();
        setOpenModalOpen(true);
      } else if (!isInput && e.key === " " && activeTabId) {
        e.preventDefault();
        triggerFit();
      } else if (e.key === "Escape" && !isInput) {
        selectEntity(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTabId, setNewModalOpen, setOpenModalOpen, triggerFit, selectEntity]);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[var(--nx-base)] text-[var(--nx-text-primary)] font-sans antialiased">
      {/* 1. Top Application Chrome */}
      <WorkstationHeader />

      {/* 2. Investigation Workspace Tabs Bar */}
      <InvestigationTabBar />

      {/* 3. Central Workspace Canvas */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        {/* Left Panel: Entities, Filters, Tools (only when active tab is open) */}
        {activeTabId && leftPanelOpen && (
          <aside className="flex w-64 shrink-0 flex-col border-r border-[var(--nx-border)] bg-[var(--nx-surface-1)] z-10 overflow-hidden relative">
            <EntityListPanel investigationId={activeTabId} />
          </aside>
        )}

        {/* Right Area: Graph + Bottom Drawer */}
        <div className="flex flex-1 flex-col min-w-0 min-h-0 relative">
          {/* Center Canvas: Knowledge Graph or Blank Canvas */}
          <main className="relative flex flex-1 min-w-0 flex-col overflow-hidden bg-[var(--nx-base)]">
            {activeTabId ? (
              <>
                <GraphLegend investigationId={activeTabId} />
                <GraphView investigationId={activeTabId} />
              </>
            ) : (
              <BlankCanvas />
            )}
          </main>

          {/* Bottom Drawer: Activity, AI Intel, Reports (collapsible) */}
          {activeTabId && <BottomDrawer investigationId={activeTabId} />}
        </div>
      </div>

      {/* 4. Bottom Status Bar */}
      <WorkstationStatusBar />

      {/* 5. Modals */}
      <NewInvestigationModal />
      <OpenInvestigationModal />
    </div>
  );
}
