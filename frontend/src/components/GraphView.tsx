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
            color: "#111827",
            "font-size": "10px",
            "font-family": "Inter, system-ui, sans-serif",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 4,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "border-width": 1,
            "border-color": "#ffffff",
            width: 26,
            height: 26,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#2563eb",
            width: 34,
            height: 34,
            "z-index": 999,
          },
        },
        {
          selector: "node.dimmed",
          style: { opacity: 0.2 },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": DEFAULT_EDGE_COLOR,
            "curve-style": "bezier",
            "target-arrow-color": DEFAULT_EDGE_COLOR,
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "font-size": "8px",
            label: "data(displayLabel)",
            color: "#6b7280",
            "text-rotation": "autorotate",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.8,
            "text-background-padding": "1px",
            opacity: 0.7,
          },
        },
        {
          selector: "edge.dimmed",
          style: { opacity: 0.05 },
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
        className="cy-container h-full w-full rounded-md border border-gray-200"
      />
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80">
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
        <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-white/90 px-2 py-1 text-xs text-gray-600 shadow">
          {data.nodes.length} nodes · {data.edges.length} edges · click a node to inspect
        </div>
      )}
    </div>
  );
}
