/**
 * GraphScene — R3F scene composition for the Knowledge Graph.
 *
 * Assembles: CameraController, EdgeLines, NodeInstances, NodeLabels
 * inside an R3F Canvas. Simulation stepping is driven by useFrame
 * inside the Canvas for zero React re-renders during simulation.
 */

import React, { useMemo, useCallback, useEffect, useState, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { useForceSimulation, SimNode, SimLink } from './simulation/use-force-layout';
import NodeInstances from './nodes/NodeInstances';
import EdgeLines from './edges/EdgeLines';
import CameraController from './camera/CameraController';
import NodeLabels from './labels/NodeLabels';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';
import { getNodeColor, getNodeEmissiveColor, getShapeType, EDGE_LABEL_COLORS, getCommunityColor, getCommunityEmissiveColor } from '../constants';
import { getArchetype, isHubArchetype, ARCHETYPE_EMISSIVE_STRENGTH, ARCHETYPE_SCALE } from './nodes/archetypes';
import PostFX from './effects/PostFX';

function getEdgeColor(label: string): string {
  const key = label.toUpperCase();
  return EDGE_LABEL_COLORS[key] ?? '#6b7280';
}

interface GraphSceneProps {
  nodes: ExplorerNode[];
  edges: ExplorerEdge[];
  isLoading: boolean;
  selectedNode: ExplorerNode | null;
  onSelectNode: (node: ExplorerNode | null) => void;
  nodeBrightness: Map<string, number>;
  activeIgnitionPoints: string[];
  selectedPath: { source: string; target: string; path: string[] } | null;
  highlightedLabels?: Set<string>;
  /** When true, use community-based coloring instead of label-based. */
  communityLens?: boolean;
}

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
  highlightedLabels,
  nodeBrightness,
  simStep,
  simGetPositions,
  simGetIsRunning,
  is2D,
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
  highlightedLabels: Set<string>;
  nodeBrightness: Map<string, number>;
  simStep: () => void;
  simGetPositions: () => { nodes: SimNode[]; links: SimLink[] };
  simGetIsRunning: () => boolean;
  is2D: boolean;
}) {
  return (
    <>
      <color attach="background" args={['#0a0a12']} />
      <ambientLight intensity={0.6} />
      <pointLight position={[500, 500, 500]} intensity={0.6} color="#c8d0e0" />
      <pointLight position={[-300, -200, -400]} intensity={0.3} color="#8090b0" />
      <CameraController
        nodes={simNodes}
        width={width}
        height={height}
        selectedId={selectedId}
        is2D={is2D}
        simGetIsRunning={simGetIsRunning}
      />
      <EdgeLines links={simLinks} nodes={simNodes} selectedPath={selectedPath} ignitionSet={ignitionSet} simGetIsRunning={simGetIsRunning} />
      <NodeInstances
        nodes={simNodes}
        ignitionSet={ignitionSet}
        selectedId={selectedId}
        pathSet={pathSet}
        onNodeClick={onNodeClick}
        highlightedLabels={highlightedLabels}
        nodeBrightness={nodeBrightness}
        simStep={simStep}
        simGetPositions={simGetPositions}
        simGetIsRunning={simGetIsRunning}
      />
      <NodeLabels
        nodes={simNodes}
        ignitionSet={ignitionSet}
        selectedId={selectedId}
        maxLabels={1000}
        nodeBrightness={nodeBrightness}
      />
      <PostFX />
    </>
  );
}

export default function GraphScene({
  nodes,
  edges,
  isLoading,
  selectedNode,
  onSelectNode,
  nodeBrightness,
  activeIgnitionPoints,
  selectedPath,
  highlightedLabels: externalHighlightedLabels,
  communityLens = false,
}: GraphSceneProps) {
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [internalHighlightedLabels] = useState<Set<string>>(new Set());
  const highlightedLabels = externalHighlightedLabels ?? internalHighlightedLabels;
  const containerRef = useRef<HTMLDivElement>(null);

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

  const simInput = useMemo(() => {
    if (nodes.length === 0) return null;

    const allDegrees = nodes.map(n => n.degree ?? 0);

    const simNodes: SimNode[] = nodes.map(n => {
      const degree = n.degree ?? 0;
      const label = n.label;
      const isHub = isHubArchetype(degree, allDegrees);
      const archetype = isHub ? 'hub' : getArchetype(label);
      const emissiveStrength = ARCHETYPE_EMISSIVE_STRENGTH[archetype as keyof typeof ARCHETYPE_EMISSIVE_STRENGTH] ?? 0.5;
      const roleScale = ARCHETYPE_SCALE[archetype as keyof typeof ARCHETYPE_SCALE] ?? 1.0;

      // Choose color based on active lens
      const color = communityLens ? getCommunityColor(n.community_id) : getNodeColor(label);
      const emissiveColor = communityLens ? getCommunityEmissiveColor(n.community_id) : getNodeEmissiveColor(label);

      return {
        id: n.id,
        name: n.name,
        label,
        score: n.score,
        degree,
        brightness: 0.3,
        color,
        emissiveColor,
        shapeType: getShapeType(label),
        archetype,
        isHub,
        emissiveStrength,
        roleScale,
        properties: n.properties,
      };
    });

    const validNodeIds = new Set(nodes.map(n => n.id));

    const simLinks: SimLink[] = edges
      .filter(e => validNodeIds.has(e.source) && validNodeIds.has(e.target))
      .map(e => ({
        source: e.source,
        target: e.target,
        label: e.label,
        weight: e.weight,
        color: getEdgeColor(e.label),
      }));

    return { nodes: simNodes, links: simLinks };
  }, [nodes, edges, communityLens]);

  const is2D = false;

  const simOptions = useMemo(() => ({
    width: dimensions?.width ?? 800,
    height: dimensions?.height ?? 600,
    dimension: is2D ? '2d' as const : '3d' as const,
  }), [dimensions?.width, dimensions?.height, is2D]);

  const { step, getPositions, reheat, getIsRunning } = useForceSimulation(simInput, simOptions);

  const prevNodeCount = useRef(0);
  useEffect(() => {
    if (nodes.length > prevNodeCount.current && prevNodeCount.current > 0) {
      reheat(0.3);
    }
    prevNodeCount.current = nodes.length;
  }, [nodes.length, reheat]);

  const ignitionSet = useMemo(() => new Set(activeIgnitionPoints), [activeIgnitionPoints]);
  const pathSet = useMemo(() => {
    if (!selectedPath?.path) return new Set<string>();
    return new Set(selectedPath.path);
  }, [selectedPath]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      if (selectedNode?.id === nodeId) {
        onSelectNode(null);
      } else {
        const originalNode = nodes.find(n => n.id === nodeId);
        if (originalNode) {
          onSelectNode(originalNode);
        }
      }
    },
    [selectedNode, onSelectNode, nodes]
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectedNode) {
        onSelectNode(null);
      }
    };

    el.addEventListener('keydown', handleKeyDown);
    return () => el.removeEventListener('keydown', handleKeyDown);
  }, [selectedNode, onSelectNode]);

  const announcementRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!announcementRef.current) return;
    if (selectedNode) {
      announcementRef.current.textContent = `Selected ${selectedNode.label}: ${selectedNode.name}, degree ${selectedNode.degree ?? 0}`;
    } else {
      announcementRef.current.textContent = 'No node selected';
    }
  }, [selectedNode]);

  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  const positions = getPositions();

  const content = (() => {
    if (isLoading && nodes.length === 0) {
      return (
        <div className="h-full w-full flex flex-col items-center justify-center gap-4">
          <div className="w-full max-w-[400px] space-y-3 px-6">
            <div className="h-6 rounded-lg animate-pulse" style={{ background: 'var(--color-border)', opacity: 0.15 }} />
            <div className="flex gap-3">
              <div className="h-4 w-20 rounded animate-pulse" style={{ background: 'var(--color-border)', opacity: 0.1 }} />
              <div className="h-4 w-16 rounded animate-pulse" style={{ background: 'var(--color-border)', opacity: 0.1 }} />
              <div className="h-4 w-24 rounded animate-pulse" style={{ background: 'var(--color-border)', opacity: 0.1 }} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-12 rounded-lg animate-pulse" style={{ background: 'var(--color-border)', opacity: 0.08 }} />
              ))}
            </div>
          </div>
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
            Knowledge Graph
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Click &quot;Explore&quot; to load the knowledge graph.
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
      <div ref={containerRef} className="h-full w-full flex items-center justify-center" role="application" aria-label="Knowledge Graph Explorer">
        {content}
        <div ref={announcementRef} role="status" aria-live="polite" className="sr-only" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="h-full w-full overflow-hidden relative"
      role="application"
      aria-label="Knowledge Graph Explorer"
      tabIndex={0}
      onContextMenu={e => e.preventDefault()}
    >
      <div ref={announcementRef} role="status" aria-live="polite" className="sr-only" />
      <Canvas
        orthographic={is2D}
        camera={
          is2D
            ? { near: 0.1, far: 10000, position: [0, 0, 1000], left: -600, right: 600, top: 600, bottom: -600, zoom: 1 }
            : { fov: 75, near: 0.1, far: 10000, position: [0, 0, 800] }
        }
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
        }}
        dpr={prefersReducedMotion ? 1 : [1, 1.5]}
        style={{ width: '100%', height: '100%' }}
        frameloop={prefersReducedMotion ? 'demand' : 'always'}
      >
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
          highlightedLabels={highlightedLabels}
          nodeBrightness={nodeBrightness}
          simStep={step}
          simGetPositions={getPositions}
          simGetIsRunning={getIsRunning}
          is2D={is2D}
        />
      </Canvas>
    </div>
  );
}
