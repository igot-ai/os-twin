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
  const fullscreenContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [rawFullscreenDims, setFullscreenDims] = useState<{ width: number; height: number } | null>(null);
  const fullscreenDims = isFullscreen ? rawFullscreenDims : null;

  // Measure fullscreen container — only runs when isFullscreen is true
  useEffect(() => {
    if (!isFullscreen) return;
    const el = fullscreenContainerRef.current;
    if (!el) return;
    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) setFullscreenDims({ width: Math.floor(width), height: Math.floor(height) });
    };
    measure();
    const obs = new ResizeObserver(measure);
    obs.observe(el);
    const t = setTimeout(measure, 100);
    return () => { obs.disconnect(); clearTimeout(t); };
  }, [isFullscreen]);
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let rafId: number | null = null;
    let settled = false;

    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        setDimensions(prev => {
          // Only update state if dimensions actually changed (avoids re-render loops)
          if (prev && prev.width === Math.floor(width) && prev.height === Math.floor(height)) {
            return prev;
          }
          return { width: Math.floor(width), height: Math.floor(height) };
        });
        settled = true;
      }
    };

    // Poll with rAF until we get a valid measurement.
    // This handles the case where the container isn't laid out yet on first mount
    // (e.g., parent flex/grid hasn't resolved, or the dynamic import shifts layout).
    const pollUntilSettled = () => {
      measure();
      if (!settled) {
        rafId = requestAnimationFrame(pollUntilSettled);
      }
    };
    pollUntilSettled();

    // ResizeObserver for all subsequent layout changes
    const obs = new ResizeObserver(() => measure());
    obs.observe(el);

    return () => {
      obs.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, []);

  // Track node count to only zoom-to-fit when graph changes initially
  const prevNodeCount = useRef(0);
  const handleEngineStop = useCallback(() => {
    if (nodes.length > 0 && nodes.length !== prevNodeCount.current) {
      graphRef.current?.zoomToFit?.(600, 100); // Smooth zoom, 100px padding
      prevNodeCount.current = nodes.length;
    }
  }, [nodes.length]);

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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

  // Adjust forces to spread nodes out and prevent shaking/clumping
  useEffect(() => {
    if (graphRef.current) {
      const chargeForce = graphRef.current.d3Force('charge');
      if (chargeForce) {
        chargeForce.strength(-1500);
        chargeForce.distanceMax(3000);
      }

      const linkForce = graphRef.current.d3Force('link');
      if (linkForce) {
        linkForce.distance(250);
      }

      graphRef.current.d3ReheatSimulation?.();
    }
  }, [graphData, dimensions, isFullscreen]);

  // Loading state
  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center">
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
      <div className="h-full w-full flex items-center justify-center">
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

  // Collect unique labels for legend, filtering out 'Relationship' and sorting by node count
  const labelCounts = new Map<string, number>();
  nodes.forEach(n => {
    if (n.label.toLowerCase() !== 'relationship') {
      labelCounts.set(n.label, (labelCounts.get(n.label) || 0) + 1);
    }
  });
  const labels = Array.from(labelCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([label]) => label);

  const graphContent = (dims: { width: number; height: number }) => (
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      width={dims.width}
      height={dims.height}
      nodeRelSize={6}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nodeVal={(node: any) => node.score}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      nodeColor={(node: any) => node.color}
      linkColor={() => '#6b7280'}
      nodeCanvasObject={paintNode}
      onNodeClick={handleNodeClick}
      onEngineStop={handleEngineStop}
      enableZoomInteraction={true}
      enablePanInteraction={true}
      enableNodeDrag={true}
      d3AlphaDecay={0.05}     // Faster decay so it settles instead of vibrating indefinitely
      d3VelocityDecay={0.6}   // Higher friction to dampen shaking
      cooldownTicks={250}     // Allow enough ticks for it to nicely float into balance
    />
  );

  // Fullscreen overlay
  if (isFullscreen) {
    return (
      <div
        className="fixed inset-0 z-50 flex flex-col"
        style={{ background: 'var(--color-background)' }}
      >
        {/* Fullscreen toolbar */}
        <div
          className="flex items-center justify-between px-4 py-2 border-b shrink-0"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--color-primary)' }}>hub</span>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-main)' }}>Knowledge Graph</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              {stats.node_count} nodes · {stats.edge_count} edges
            </span>
          </div>
          <button
            onClick={() => setIsFullscreen(false)}
            className="p-2 rounded-lg transition-colors hover:bg-surface-hover"
            title="Exit fullscreen"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--color-text-muted)' }}>close_fullscreen</span>
          </button>
        </div>

        {/* Legend */}
        {labels.length > 1 && (
          <div className="flex flex-wrap gap-2 px-4 py-2 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
            {labels.map(label => (
              <span key={label} className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: getNodeColor(label) }} />
                {label}
              </span>
            ))}
          </div>
        )}

        {/* Graph fills remaining space */}
        <div className="flex-1 relative overflow-hidden" ref={fullscreenContainerRef}>
          {fullscreenDims ? graphContent(fullscreenDims) : null}
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden relative">
      {/* Toolbar: legend + fullscreen */}
      <div className="absolute top-2 right-2 z-10 flex items-center gap-1.5">
        <button
          onClick={() => setIsFullscreen(true)}
          className="p-1.5 rounded-lg border transition-colors hover:bg-surface-hover"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-background)' }}
          title="Fullscreen"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>open_in_full</span>
        </button>
      </div>

      {/* Legend */}
      {labels.length > 1 && (
        <div className="absolute bottom-2 left-2 z-10 flex flex-wrap gap-1.5 max-w-[60%]">
          {labels.slice(0, 10).map(label => (
            <span
              key={label}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] border"
              style={{
                color: getNodeColor(label),
                borderColor: `${getNodeColor(label)}30`,
                background: `${getNodeColor(label)}10`,
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: getNodeColor(label) }} />
              {label}
            </span>
          ))}
          {labels.length > 10 && (
            <span className="text-[9px] px-1.5 py-0.5" style={{ color: 'var(--color-text-faint)' }}>
              +{labels.length - 10}
            </span>
          )}
        </div>
      )}

      {/* Force graph */}
      {dimensions ? graphContent(dimensions) : (
        <div className="h-full w-full flex items-center justify-center animate-pulse">
          <div className="w-12 h-12 rounded-full" style={{ background: 'var(--color-border)', opacity: 0.3 }} />
        </div>
      )}
    </div>
  );
}

