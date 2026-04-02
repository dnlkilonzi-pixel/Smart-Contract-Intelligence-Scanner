"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import type { WalletGraph, GraphNode, GraphEdge } from "@/lib/types";
import { getWalletGraph } from "@/lib/api";
import { Loader2, Network } from "lucide-react";
import clsx from "clsx";

interface Props {
  address: string;
}

const NODE_COLOR: Record<string, string> = {
  wallet: "#0ea5e9",
  contract: "#f59e0b",
};

const EDGE_COLOR: Record<string, string> = {
  deployed: "#f59e0b",
  called: "#64748b",
  funded: "#10b981",
};

type SimNode = GraphNode & d3.SimulationNodeDatum;
type SimEdge = { source: SimNode; target: SimNode; type: string };

export default function WalletGraph({ address }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [graph, setGraph] = useState<WalletGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    setError(null);
    getWalletGraph(address, 1)
      .then(setGraph)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address]);

  useEffect(() => {
    if (!graph || !svgRef.current) return;

    const el = svgRef.current;
    const { width, height } = el.getBoundingClientRect();

    // Clear previous render
    d3.select(el).selectAll("*").remove();

    const svg = d3
      .select(el)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("preserveAspectRatio", "xMidYMid meet");

    // Arrow marker
    svg
      .append("defs")
      .append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 18)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#64748b");

    const nodes: SimNode[] = graph.nodes.map((n) => ({ ...n }));
    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    const edges: SimEdge[] = graph.edges
      .map((e) => ({
        source: nodeById.get(
          typeof e.source === "string" ? e.source : (e.source as GraphNode).id
        )!,
        target: nodeById.get(
          typeof e.target === "string" ? e.target : (e.target as GraphNode).id
        )!,
        type: e.type,
      }))
      .filter((e) => e.source && e.target);

    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(edges)
          .id((d) => d.id)
          .distance(100)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(30));

    // Zoom container
    const g = svg.append("g");
    svg.call(
      d3.zoom<SVGSVGElement, unknown>().on("zoom", (event) =>
        g.attr("transform", event.transform)
      )
    );

    // Edges
    const link = g
      .append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("stroke", (d) => EDGE_COLOR[d.type] ?? "#64748b")
      .attr("stroke-opacity", 0.7)
      .attr("stroke-width", 1.5)
      .attr("marker-end", "url(#arrow)");

    // Nodes
    const node = g
      .append("g")
      .selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => (d.id === address.toLowerCase() ? 14 : 9))
      .attr("fill", (d) => NODE_COLOR[d.type] ?? "#94a3b8")
      .attr("stroke", "#1e293b")
      .attr("stroke-width", 2)
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Labels
    const label = g
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => d.label)
      .attr("font-size", 9)
      .attr("fill", "#94a3b8")
      .attr("text-anchor", "middle")
      .attr("dy", 22);

    // Tooltip
    node.append("title").text((d) => `${d.type}: ${d.id}`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);
      node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      label.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
  }, [graph, address]);

  return (
    <div className="rounded-2xl bg-slate-800 border border-slate-700 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700">
        <Network size={14} className="text-sky-400" />
        <span className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Wallet Relationship Graph
        </span>
        {graph && (
          <span className="ml-auto text-xs text-slate-500">
            {graph.stats.node_count} nodes · {graph.stats.edge_count} edges
          </span>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-slate-700/50 text-[10px] text-slate-500">
        <LegendDot color="#0ea5e9" label="Wallet" />
        <LegendDot color="#f59e0b" label="Contract" />
        <LegendLine color="#f59e0b" label="Deployed" />
        <LegendLine color="#10b981" label="Funded" />
        <LegendLine color="#64748b" label="Called" />
      </div>

      {/* Graph canvas */}
      <div className="relative h-80">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 size={24} className="animate-spin text-sky-500" />
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm">
            {error}
          </div>
        )}
        {!loading && !error && graph?.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-600 text-sm">
            No relationship data found.
          </div>
        )}
        <svg ref={svgRef} className="w-full h-full" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span
        className="w-2.5 h-2.5 rounded-full inline-block"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function LegendLine({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
