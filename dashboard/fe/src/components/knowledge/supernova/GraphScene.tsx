/**
 * GraphScene — R3F scene composition for Supernova Explorer.
 *
 * Assembles: CameraController, EdgeLines, NodeInstances, NodeLabels
 * inside an R3F Canvas. Reads positions from the force simulation
 * via the useForceSimulation hook.
 */

import React, { useMemo, useCallback, useEffect, useState, useRef } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { useForceSimulation, SimNode, SimLink } from './useForceSimulation';
import NodeInstances from './NodeInstances';
import EdgeLines from './EdgeLines';
import CameraController from './CameraController';
import NodeLabels from './NodeLabels';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';
import { getNodeColor, getShapeType } from '../constants';

// ---------------------------------------------------------------------------
// Edge color by relationship label
// ---------------------------------------------------------------------------

const EDGE_LABEL_COLORS: Record<string, string> = {
  MENTIONS: '#60a5fa',
  KNOWS: '#a78bfa',
  RELATED_TO: '#34d399',
  REFERENCES: '#fbbf24',
  USES: '#f472b6',
  CONTAINS: '#fb923c',
  RELATES: '#6b7280',
};

function getEdgeColor(label: string): string {
  const key = label.toUpperCase();
  return EDGE_LABEL_COLORS[key] ?? '#6b7280';
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GraphSceneProps {
  nodes: ExplorerNode[];
  edges: ExplorerEdge[];
  isLoading: boolean;
  selectedNode: ExplorerNode | null;
  onSelectNode: (node: ExplorerNode | null) => void;
  onIgnite: (nodeId: string) => void;
  nodeBrightness: Map<string, number>;
  activeIgnitionPoints: string[];
  selectedPath: { source: string; target: string; path: string[] } | null;
}

// ---------------------------------------------------------------------------
// Inner scene component (inside Canvas, has R3F context)
// ---------------------------------------------------------------------------

function SceneContent({
  simNodes,
  simLinks,
  ignitionSet,
  selectedId,
  pathSet,
  selectedPath,
  onNodeClick,
  width,
  height,
  zoomLevel,
  highlightedLabels,
}: {
  simNodes: SimNode[];
  simLinks: SimLink[];
  ignitionSet: Set<string>;
  selectedId: string | null;
  pathSet: Set<string>;
  selectedPath: { source: string; target: string; path: string[] } | null;
  onNodeClick: (nodeId: string) => void;
  width: number;
  height: number;
  zoomLevel: number;
  highlightedLabels: Set<string>;
}) {
  return (
    <>
      <color attach="background" args={['#f8fafc']} />
      <ambientLight intensity={1.0} />
      <CameraController nodes={simNodes} width={width} height={height} />
      <EdgeLines links={simLinks} selectedPath={selectedPath} />
      <NodeInstances
        nodes={simNodes}
        ignitionSet={ignitionSet}
        selectedId={selectedId}
        pathSet={pathSet}
        onNodeClick={onNodeClick}
        highlightedLabels={highlightedLabels}
      />
      <NodeLabels
        nodes={simNodes}
        ignitionSet={ignitionSet}
        selectedId={selectedId}
        showLabels={zoomLevel > 0.3}
        maxLabels={150}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Zoom tracker — reads camera distance to estimate zoom level
// ---------------------------------------------------------------------------

function ZoomTracker({ onZoomChange }: { onZoomChange: (zoom: number) => void }) {
  const { camera } = useThree();

  useFrame(() => {
    // Approximate zoom: how "close" the camera is
    // Higher values = more zoomed in
    const dist = camera.position.z;
    const zoom = Math.max(0.01, 1000 / dist);
    onZoomChange(zoom);
  });

  return null;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GraphScene({
  nodes,
  edges,
  isLoading,
  selectedNode,
  onSelectNode,
  onIgnite,
  nodeBrightness,
  activeIgnitionPoints,
  selectedPath,
}: GraphSceneProps) {
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [highlightedLabels, setHighlightedLabels] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);

  // ---- Measure container ----
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let settled = false;
    let rafId: number | null = null;

    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        setDimensions(prev => {
          if (prev && prev.width === Math.floor(width) && prev.height === Math.floor(height)) {
            return prev;
          }
          return { width: Math.floor(width), height: Math.floor(height) };
        });
        settled = true;
      }
    };

    const poll = () => {
      measure();
      if (!settled) {
        rafId = requestAnimationFrame(poll);
      }
    };
    poll();

    const obs = new ResizeObserver(() => measure());
    obs.observe(el);

    return () => {
      obs.disconnect();
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, []);

  // ---- Transform explorer data → simulation input ----
  const simInput = useMemo(() => {
    if (nodes.length === 0) return null;

    const simNodes: SimNode[] = nodes.map(n => ({
      id: n.id,
      name: n.name,
      label: n.label,
      score: n.score,
      degree: n.degree ?? 0,
      brightness: nodeBrightness.get(n.id) ?? 0.3,
      color: getNodeColor(n.label),
      shapeType: getShapeType(n.label),
      properties: n.properties,
    }));

    const simLinks: SimLink[] = edges.map(e => ({
      source: e.source,
      target: e.target,
      label: e.label,
      weight: e.weight,
      color: getEdgeColor(e.label),
    }));

    return { nodes: simNodes, links: simLinks };
  }, [nodes, edges, nodeBrightness]);

  // ---- Run force simulation ----
  const { getPositions, reheat } = useForceSimulation(simInput, {
    width: dimensions?.width ?? 800,
    height: dimensions?.height ?? 600,
  });

  // Reheat when new nodes are added
  const prevNodeCount = useRef(0);
  useEffect(() => {
    if (nodes.length > prevNodeCount.current && prevNodeCount.current > 0) {
      reheat(0.3);
    }
    prevNodeCount.current = nodes.length;
  }, [nodes.length, reheat]);

  // ---- Build lookup sets ----
  const ignitionSet = useMemo(() => new Set(activeIgnitionPoints), [activeIgnitionPoints]);
  const pathSet = useMemo(() => {
    if (!selectedPath?.path) return new Set<string>();
    return new Set(selectedPath.path);
  }, [selectedPath]);

  // ---- Node click handler ----
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      if (selectedNode?.id === nodeId) {
        onSelectNode(null);
      } else {
        const originalNode = nodes.find(n => n.id === nodeId);
        if (originalNode) {
          onSelectNode(originalNode);
          onIgnite(nodeId);
        }
      }
    },
    [selectedNode, onSelectNode, onIgnite, nodes]
  );

  // ---- Get current positions from simulation ----
  const positions = getPositions();

  // ---- Loading/empty/measuring states (all use containerRef so ResizeObserver works) ----
  const content = (() => {
    if (isLoading && nodes.length === 0) {
      return (
        <div className="text-center space-y-2">
          <div
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }}
          />
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Loading explorer...</p>
        </div>
      );
    }

    if (nodes.length === 0) {
      return (
        <div className="text-center space-y-2">
          <span className="material-symbols-outlined text-[32px]" style={{ color: 'var(--color-text-muted)' }}>
            explore
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            Supernova Explorer
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Click &quot;Explore&quot; to load the knowledge graph and ignite connections.
          </p>
        </div>
      );
    }

    if (!dimensions) {
      return (
        <div className="h-full w-full flex items-center justify-center animate-pulse">
          <div className="w-12 h-12 rounded-full" style={{ background: 'var(--color-border)', opacity: 0.2 }} />
        </div>
      );
    }

    return null;
  })();

  if (content) {
    return (
      <div ref={containerRef} className="h-full w-full flex items-center justify-center">
        {content}
      </div>
    );
  }

  // ---- Legend data ----
  const labelSet = new Set(nodes.map(n => n.label));
  const labels = Array.from(labelSet).sort();
  const edgeLabelSet = new Set(edges.map(e => e.label).filter(l => l && l !== 'RELATES'));
  const edgeLabels = Array.from(edgeLabelSet).sort();

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden relative">
      {/* R3F Canvas */}
      <Canvas
        orthographic={false}
        camera={{
          fov: 75,
          near: 0.1,
          far: 10000,
          position: [0, 0, 800],
        }}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
        }}
        dpr={[1, 2]}
        style={{ width: '100%', height: '100%' }}
      >
        <ZoomTracker onZoomChange={setZoomLevel} />
        <SceneContent
          simNodes={positions.nodes}
          simLinks={positions.links}
          ignitionSet={ignitionSet}
          selectedId={selectedNode?.id ?? null}
          pathSet={pathSet}
          selectedPath={selectedPath}
          onNodeClick={handleNodeClick}
          width={dimensions!.width}
          height={dimensions!.height}
          zoomLevel={zoomLevel}
          highlightedLabels={highlightedLabels}
        />
      </Canvas>

      {/* HTML overlays — legends, badges */}

      {/* Node legend — bottom left — click to highlight label */}
      {labels.length > 1 && (
        <div className="absolute bottom-2 left-2 z-10 flex flex-wrap gap-1.5 max-w-[60%]">
          {labels.slice(0, 12).map(label => {
            const isHighlighted = highlightedLabels.has(label);
            const color = getNodeColor(label);
            return (
              <button
                key={label}
                onClick={() => {
                  setHighlightedLabels(prev => {
                    const next = new Set(prev);
                    if (next.has(label)) {
                      next.delete(label);
                    } else {
                      next.add(label);
                    }
                    return next;
                  });
                }}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] border transition-all cursor-pointer"
                style={{
                  color: isHighlighted ? color : `${color}80`,
                  borderColor: isHighlighted ? color : `${color}30`,
                  background: isHighlighted ? `${color}18` : `${color}08`,
                  fontWeight: isHighlighted ? 600 : 400,
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color, opacity: isHighlighted ? 1 : 0.5 }} />
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Edge legend — bottom right */}
      {edgeLabels.length > 0 && (
        <div className="absolute bottom-2 right-2 z-10 flex flex-wrap gap-1.5 max-w-[40%]">
          {edgeLabels.slice(0, 6).map(label => (
            <span
              key={label}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px]"
              style={{ color: getEdgeColor(label), opacity: 0.7 }}
            >
              <span className="w-3 h-0.5 shrink-0" style={{ background: getEdgeColor(label) }} />
              {label}
            </span>
          ))}
        </div>
      )}

      {/* Ignition count badge — top right */}
      {activeIgnitionPoints.length > 0 && (
        <div className="absolute top-2 right-2 z-10">
          <span
            className="px-2 py-0.5 rounded-full text-[9px] font-medium"
            style={{
              background: 'var(--color-primary-muted)',
              color: 'var(--color-primary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {activeIgnitionPoints.length} ignited
          </span>
        </div>
      )}
    </div>
  );
}
