import { useEffect, useRef } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useInvestigationGraph } from "../hooks/useApi";
import { useWorkspaceStore } from "../store/workspace";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";
import {
  DEFAULT_EDGE_COLOR,
  DEFAULT_NODE_COLOR,
  NODE_TYPE_COLORS,
} from "../lib/format";

interface GraphViewProps {
  investigationId: string;
}

const getIconSvg = (type: string, color: string) => {
  let path = '';
  const c = color;
  switch (type.toLowerCase()) {
    case 'domain':
    case 'url':
      path = `<circle cx="12" cy="12" r="10" stroke="${c}" fill="none" stroke-width="2"/><path d="M2 12h20" stroke="${c}" stroke-width="2"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" stroke="${c}" fill="none" stroke-width="2"/>`;
      break;
    case 'username':
    case 'person':
      path = `<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" stroke="${c}" fill="none" stroke-width="2"/><circle cx="12" cy="7" r="4" stroke="${c}" fill="none" stroke-width="2"/>`;
      break;
    case 'technology':
      path = `<rect width="20" height="14" x="2" y="3" rx="2" stroke="${c}" fill="none" stroke-width="2"/><line x1="8" x2="16" y1="21" y2="21" stroke="${c}" stroke-width="2"/><line x1="12" x2="12" y1="17" y2="21" stroke="${c}" stroke-width="2"/>`;
      break;
    case 'repository':
      path = `<polyline points="16 18 22 12 16 6" stroke="${c}" fill="none" stroke-width="2"/><polyline points="8 6 2 12 8 18" stroke="${c}" fill="none" stroke-width="2"/>`;
      break;
    case 'link':
      path = `<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="${c}" fill="none" stroke-width="2"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="${c}" fill="none" stroke-width="2"/>`;
      break;
    default:
      path = `<circle cx="12" cy="12" r="10" stroke="${c}" fill="none" stroke-width="2"/>`;
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
  return `data:image/svg+xml;base64,${btoa(svg)}`;
};

const getNodeShape = (type: string) => {
  const t = type.toLowerCase();
  if (t === 'technology' || t === 'repository') return 'roundrectangle';
  if (t === 'organization') return 'hexagon';
  if (t === 'threatindicator') return 'diamond';
  if (t === 'person' || t === 'username') return 'ellipse';
  return 'ellipse';
};

const getGraphStyle = (theme: string) => [
  {
    selector: "node",
    style: {
      "shape": "data(shape)" as any,
      "background-color": theme === "light" ? "#ffffff" : "#0f172a",
      label: "data(displayLabel)",
      color: theme === "light" ? "#0f172a" : "#cbd5e1",
      "font-size": "10px",
      "font-family": "Inter, system-ui, sans-serif",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 6,
      "text-wrap": "wrap",
      "text-max-width": "140px",
      "border-width": 1.5,
      "border-color": "data(color)",
      width: 36,
      height: 36,
      "background-image": "data(iconSvg)",
      "background-width": "55%",
      "background-height": "55%",
      "background-image-opacity": 1,
      "text-background-color": theme === "light" ? "#ffffff" : "#0f1420",
      "text-background-opacity": 0.95,
      "text-background-padding": "4px",
      "text-background-shape": "roundrectangle",
      "text-border-width": 1,
      "text-border-color": "data(color)",
      "text-border-opacity": 0.4,
    },
  },
  {
    selector: "node[isSeed]",
    style: {
      "border-width": 2,
      "width": 42,
      "height": 42,
      "text-border-opacity": 0.8,
      "font-weight": "bold",
      "color": theme === "light" ? "#0284c7" : "#38bdf8",
      "border-color": theme === "light" ? "#0284c7" : "#38bdf8",
    }
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": theme === "light" ? "#0284c7" : "#22d3ee",
      width: 44,
      height: 44,
      "z-index": 999,
    },
  },
  {
    selector: "node.dimmed",
    style: { opacity: 0.15 },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": theme === "light" ? "#94a3b8" : DEFAULT_EDGE_COLOR,
      "curve-style": "bezier",
      "target-arrow-color": theme === "light" ? "#94a3b8" : DEFAULT_EDGE_COLOR,
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.8,
      "font-size": "9px",
      "font-family": "monospace",
      label: "data(displayLabel)",
      color: theme === "light" ? "#64748b" : "#94a3b8",
      "text-rotation": "autorotate",
      "text-background-color": theme === "light" ? "#f8fafc" : "#0f1420",
      "text-background-opacity": 0.85,
      "text-background-padding": "2px",
      opacity: 0.7,
      "line-style": "dashed",
      "line-dash-pattern": [4, 4],
    },
  },
  {
    selector: "edge[relationship_type = 'commits_to']",
    style: {
      "line-style": "solid",
      "line-color": theme === "light" ? "#0ea5e9" : "#38bdf8",
      "target-arrow-color": theme === "light" ? "#0ea5e9" : "#38bdf8",
      "width": 2,
    }
  },
  {
    selector: "edge.dimmed",
    style: { opacity: 0.04 },
  },
  {
    selector: "edge:selected",
    style: {
      "line-color": theme === "light" ? "#0284c7" : "#22d3ee",
      "target-arrow-color": theme === "light" ? "#0284c7" : "#22d3ee",
      opacity: 1,
      width: 2.5,
    },
  },
];

export function GraphView({ investigationId }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const { data, isLoading, error, refetch } = useInvestigationGraph(
    investigationId,
  );

  const graphTypeFilter = useWorkspaceStore((s) => s.graphTypeFilter);
  const selectedEntityId = useWorkspaceStore((s) => s.selectedEntityId);
  const selectEntity = useWorkspaceStore((s) => s.selectEntity);
  const graphLayout = useWorkspaceStore((s) => s.graphLayout);
  const fitTrigger = useWorkspaceStore((s) => s.fitTrigger);
  const theme = useWorkspaceStore((s) => s.theme);

  // Initialize cytoscape once.
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: getGraphStyle(theme) as any,
      layout: { name: "preset" },
      minZoom: 0.15,
      maxZoom: 3,
      wheelSensitivity: 0.25,
    });

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      const id = node.id();
      if (id) selectEntity(id);
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) selectEntity(null);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectEntity]);

  // Update elements when graph data changes.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !data) return;

    const elements: ElementDefinition[] = [];

    for (const n of data.nodes) {
      const d = n.data;
      const color = NODE_TYPE_COLORS[d.type] ?? DEFAULT_NODE_COLOR;
      let displayLabel = d.label || d.id.split(":").slice(1).join(":") || d.id;
      if (d.confidence != null) {
        displayLabel += ` ${Math.round(d.confidence * 100)}%`;
      }
      const isSeed = (d as any).is_seed === true || d.properties?.is_seed === true;
      if (isSeed) {
        displayLabel += "\nSEED TARGET";
      }

      elements.push({
        group: "nodes",
        data: {
          id: d.id,
          label: d.label || d.id,
          type: d.type,
          confidence: d.confidence,
          source_count: d.source_count,
          displayLabel,
          color,
          iconSvg: getIconSvg(d.type, color),
          shape: getNodeShape(d.type),
          isSeed,
        },
      });
    }

    for (const e of data.edges) {
      const d = e.data;
      const displayLabel = d.relationship_type?.replace(/_/g, " ") ?? "";
      elements.push({
        group: "edges",
        data: {
          id: d.id || `${d.source}->${d.target}`,
          source: d.source,
          target: d.target,
          relationship_type: d.relationship_type,
          confidence: d.confidence,
          displayLabel: d.confidence != null ? `${displayLabel} (${Math.round(d.confidence * 100)}%)` : displayLabel,
        },
      });
    }

    cy.elements().remove();
    cy.add(elements);
    cy.layout({
      name: "cose",
      animate: false,
      padding: 30,
      nodeRepulsion: () => 4500,
      idealEdgeLength: () => 90,
      gravity: 0.25,
      fit: true,
    } as cytoscape.LayoutOptions).run();
  }, [data]);

  // Handle graph layout changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !data || data.nodes.length === 0) return;

    const layoutOptions: Record<string, cytoscape.LayoutOptions> = {
      cose: {
        name: "cose",
        animate: true,
        animationDuration: 400,
        padding: 30,
        nodeRepulsion: () => 4500,
        idealEdgeLength: () => 90,
        gravity: 0.25,
        fit: true,
      } as cytoscape.LayoutOptions,
      concentric: {
        name: "concentric",
        animate: true,
        animationDuration: 400,
        padding: 30,
        fit: true,
      } as cytoscape.LayoutOptions,
      circle: {
        name: "circle",
        animate: true,
        animationDuration: 400,
        padding: 30,
        fit: true,
      } as cytoscape.LayoutOptions,
      grid: {
        name: "grid",
        animate: true,
        animationDuration: 400,
        padding: 30,
        fit: true,
      } as cytoscape.LayoutOptions,
    };

    const chosen = layoutOptions[graphLayout] || layoutOptions.cose;
    cy.layout(chosen).run();
  }, [graphLayout, data]);

  // Handle fit trigger
  useEffect(() => {
    if (fitTrigger === 0) return;
    const cy = cyRef.current;
    if (cy) {
      cy.fit(undefined, 30);
    }
  }, [fitTrigger]);

  // Handle dynamic theme change
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    
    // Completely replace the stylesheet with the new theme
    cy.style(getGraphStyle(theme) as any);
  }, [theme]);

  // Highlight / dim based on selected node.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass("dimmed selected");

    if (!selectedEntityId) return;

    const node = cy.getElementById(selectedEntityId);
    if (node.empty()) return;

    const neighborhood = node.closedNeighborhood();
    cy.elements().not(neighborhood).addClass("dimmed");
    node.addClass("selected");
  }, [selectedEntityId, data]);

  // Apply type filter to hide nodes/edges of deselected types.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    if (graphTypeFilter.size === 0) {
      cy.elements().style("display", "element");
      return;
    }

    cy.nodes().forEach((n) => {
      const type = n.data("type");
      const visible = graphTypeFilter.has(type);
      n.style("display", visible ? "element" : "none");
    });
    cy.edges().forEach((e) => {
      const srcVisible = e.source().style("display") !== "none";
      const tgtVisible = e.target().style("display") !== "none";
      e.style("display", srcVisible && tgtVisible ? "element" : "none");
    });
  }, [graphTypeFilter, data]);

  if (error) {
    return (
      <ErrorState
        message="Failed to load knowledge graph."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="cy-container h-full w-full rounded-md border border-[var(--nx-border)]"
      />
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[var(--nx-surface-1)]/80">
          <LoadingState label="Loading graph..." rows={1} />
        </div>
      )}
      {!isLoading && data && data.nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <EmptyState
            title="No graph data yet"
            description="Entities and relationships will appear here once collection runs."
          />
        </div>
      )}
      {data && data.nodes.length > 0 && (
        <div className="pointer-events-none absolute bottom-2 right-2 rounded-md bg-[var(--nx-surface-2)]/90 border border-[var(--nx-border)] px-2.5 py-1 text-[10px] font-mono text-[var(--nx-text-tertiary)]">
          {data.nodes.length} nodes · {data.edges.length} edges
        </div>
      )}
    </div>
  );
}
