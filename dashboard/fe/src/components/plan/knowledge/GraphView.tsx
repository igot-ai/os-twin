'use client';

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { GraphNodeResponse, GraphEdgeResponse, GraphStatsResponse } from '@/hooks/use-knowledge-graph';
import { getNodeColor } from './constants';

// Dynamic import to avoid SSR issues with react-force-graph-2d
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

interface GraphViewProps {
  nodes: GraphNodeResponse[];
  edges: GraphEdgeResponse[];
  stats: GraphStatsResponse;
  isLoading: boolean;
  selectedNode: GraphNodeResponse | null;
  onSelectNode: (node: GraphNodeResponse | null) => void;
}

// Internal graph data type for react-force-graph-2d
interface GraphNode {
  id: string;
  name: string;
  label: string;
  score: number;
  properties: Record<string, unknown>;
  color: string;
}

interface GraphLink {
  source: string;
  target: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export default function GraphView({
  nodes,
  edges,
  stats,
  isLoading,
  selectedNode,
  onSelectNode,
}: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  useEffect(() => {
    const el = containerRef.current;
    if (el) {
      const obs = new ResizeObserver(entries => {
        const { width, height } = entries[0].contentRect;
        setDimensions({ width: Math.max(300, width), height: Math.max(200, height) });
      });
      obs.observe(el);
      return () => obs.disconnect();
    }
  }, []);

  // Transform data for react-force-graph-2d
  const graphData: GraphData = useMemo(() => {
    const graphNodes: GraphNode[] = nodes.map(node => ({
      id: node.id,
      name: node.name,
      label: node.label,
      score: node.score,
      properties: node.properties,
      color: getNodeColor(node.label),
    }));

    const graphLinks: GraphLink[] = edges.map(edge => ({
      source: edge.source,
      target: edge.target,
    }));

    return { nodes: graphNodes, links: graphLinks };
  }, [nodes, edges]);

  // Node painter for canvas rendering
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isSelected = selectedNode?.id === node.id;
    const r = 6 + node.score * 3;
    const color = node.color;

    // Selection ring
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 7, 0, 2 * Math.PI);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.45;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.globalAlpha = isSelected ? 1 : 0.8;
    ctx.fill();
    ctx.globalAlpha = 1;

    // Selection border
    if (isSelected) {
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Label (only when zoomed in enough)
    if (globalScale > 0.6) {
      const label = node.name.length > 20 ? node.name.slice(0, 18) + '...' : node.name;
      ctx.font = '10px Inter, system-ui, sans-serif';
      ctx.fillStyle = 'var(--color-text-main)';
      ctx.globalAlpha = isSelected ? 1 : 0.7;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(label, node.x, node.y + r + 4);
      ctx.globalAlpha = 1;
    }
  }, [selectedNode]);

  // Handle node click
  const handleNodeClick = useCallback((node: any) => {
    if (node) {
      const originalNode = nodes.find(n => n.id === node.id);
      if (selectedNode?.id === node.id) {
        onSelectNode(null);
      } else if (originalNode) {
        onSelectNode(originalNode);
      }
    }
  }, [nodes, selectedNode, onSelectNode]);

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-2">
          <div 
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }}
          />
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Loading graph...</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-2">
          <span 
            className="material-symbols-outlined text-[32px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            hub
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            No entities yet
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Import files to extract entities and build the knowledge graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-hidden relative">
      {/* Stats badge */}
      <div 
        className="absolute top-2 right-2 rounded-full border px-3 py-1 text-[10px] z-10"
        style={{
          borderColor: 'var(--color-border)',
          background: 'var(--color-background)',
          color: 'var(--color-text-muted)',
        }}
      >
        {stats.node_count} nodes · {stats.edge_count} edges
      </div>

      {/* Force graph */}
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeRelSize={6}
        nodeVal={(node: any) => node.score}
        nodeColor={(node: any) => node.color}
        linkColor={() => '#6b7280'}
        nodeCanvasObject={paintNode}
        onNodeClick={handleNodeClick}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        enableNodeDrag={true}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        cooldownTicks={100}
      />
    </div>
  );
}
