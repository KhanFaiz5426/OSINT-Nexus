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
      style: [
        {
          selector: "node",
          style: {
            "background-color": DEFAULT_NODE_COLOR,
            label: "data(displayLabel)",
            color: theme === "light" ? "#0f172a" : "#cbd5e1",
            "font-size": "10px",
            "font-family": "Inter, system-ui, sans-serif",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 5,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "border-width": 2,
            "border-color": "data(color)",
            "background-opacity": 0.9,
            width: 30,
            height: 30,
            "text-background-color": theme === "light" ? "#ffffff" : "#0f1420",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            "text-background-shape": "roundrectangle",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": theme === "light" ? "#0284c7" : "#22d3ee",
            width: 38,
            height: 38,
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
            width: 1,
            "line-color": theme === "light" ? "#94a3b8" : DEFAULT_EDGE_COLOR,
            "curve-style": "bezier",
            "target-arrow-color": theme === "light" ? "#94a3b8" : DEFAULT_EDGE_COLOR,
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "font-size": "8px",
            label: "data(displayLabel)",
            color: theme === "light" ? "#475569" : "#64748b",
            "text-rotation": "autorotate",
            "text-background-color": theme === "light" ? "#ffffff" : "#0f1420",
            "text-background-opacity": 0.85,
            "text-background-padding": "1px",
            opacity: 0.6,
          },
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
            width: 2,
          },
        },
      ],
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
      const displayLabel = d.label || d.id.split(":").slice(1).join(":") || d.id;
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
          displayLabel,
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
    const isLight = theme === "light";
    cy.style()
      .selector("node")
      .style({
        color: isLight ? "#0f172a" : "#cbd5e1",
        "text-background-color": isLight ? "#ffffff" : "#0f1420",
      })
      .selector("node:selected")
      .style({
        "border-color": isLight ? "#0284c7" : "#22d3ee",
      })
      .selector("edge")
      .style({
        "line-color": isLight ? "#94a3b8" : DEFAULT_EDGE_COLOR,
        "target-arrow-color": isLight ? "#94a3b8" : DEFAULT_EDGE_COLOR,
        color: isLight ? "#475569" : "#64748b",
        "text-background-color": isLight ? "#ffffff" : "#0f1420",
      })
      .selector("edge:selected")
      .style({
        "line-color": isLight ? "#0284c7" : "#22d3ee",
        "target-arrow-color": isLight ? "#0284c7" : "#22d3ee",
      })
      .update();
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
