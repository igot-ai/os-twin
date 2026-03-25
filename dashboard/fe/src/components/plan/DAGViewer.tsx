'use client';

import React, { useState, useRef, useMemo } from 'react';
import useSWR from 'swr';
import { usePlanContext } from './PlanWorkspace';
import { DAG, DAGNodeRaw } from '@/types';
import { useWarRoomProgress } from '@/hooks/use-war-room';
import StateNode from './StateNode';
import DAGEdge from './DAGEdge';

// ─── Layout constants ─────────────────────────────────────────────────────────

const NODE_W = 180;
const NODE_H = 80;
const GAP_X = 80;  // horizontal gap between waves
const GAP_Y = 24;  // vertical gap between nodes in same wave

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Normalise depends_on (null | string | string[]) → string[] */
function normDeps(d: string | string[] | null | undefined): string[] {
  if (!d) return [];
  return Array.isArray(d) ? d : [d];
}

/** Sort wave keys numerically */
function sortedWaveKeys(waves: Record<string, string[]>): string[] {
  return Object.keys(waves).sort((a, b) => Number(a) - Number(b));
}

/** Get first letter of role for the badge, e.g. "engineer" → "E", "architect" → "A" */
function roleInitial(role: string): string {
  if (!role) return '?';
  return role.charAt(0).toUpperCase();
}

/** Role → color mapping for DAG badges */
const roleColorMap: Record<string, string> = {
  architect: '#8b5cf6',
  manager: '#64748b',
  engineer: '#3b82f6',
  'frontend-engineer': '#3b82f6',
  'frontend-ui-engineer': '#ec4899',
  'frontend-dag-engineer': '#06b6d4',
  'frontend-realtime-engineer': '#f59e0b',
  'frontend-interaction-engineer': '#10b981',
  'frontend-accessibility-engineer': '#ef4444',
  'build-integration-engineer': '#14b8a6',
  qa: '#10b981',
};

function getRoleColor(role: string): string {
  return roleColorMap[role] || '#6366f1';
}

/**
 * Derive positioned nodes + edges from the raw DAG API response.
 * Layout: each wave is a column; nodes within a wave are stacked vertically.
 */
function layoutDAG(dag: DAG, statusMap: Map<string, string>) {
  const waves = sortedWaveKeys(dag.waves);
  const criticalSet = new Set(dag.critical_path ?? []);

  // Position nodes by wave
  const positioned: {
    id: string;
    label: string;
    status: string;
    role: string;
    roleInitial: string;
    roleColor: string;
    x: number;
    y: number;
  }[] = [];
  const nodePositions: Record<string, { x: number; y: number }> = {};

  for (let col = 0; col < waves.length; col++) {
    const waveKey = waves[col];
    const waveNodes = dag.waves[waveKey] ?? [];
    const x = col * (NODE_W + GAP_X) + 40; // 40px left padding

    // Centre this wave's nodes vertically
    const totalH = waveNodes.length * NODE_H + (waveNodes.length - 1) * GAP_Y;
    const startY = Math.max(20, (400 - totalH) / 2);

    for (let row = 0; row < waveNodes.length; row++) {
      const nodeId = waveNodes[row];
      const y = startY + row * (NODE_H + GAP_Y);
      const dagNode = dag.nodes[nodeId];
      const role = dagNode?.role || 'unknown';
      const status = statusMap.get(nodeId) || 'pending';

      nodePositions[nodeId] = { x, y };
      positioned.push({
        id: nodeId,
        label: nodeId,
        status,
        role,
        roleInitial: roleInitial(role),
        roleColor: getRoleColor(role),
        x,
        y,
      });
    }
  }

  // Derive edges from depends_on relationships
  const edges: { from: string; to: string; is_critical: boolean }[] = [];
  for (const [nodeId, node] of Object.entries(dag.nodes)) {
    const deps = normDeps(node.depends_on);
    for (const dep of deps) {
      if (dep in dag.nodes && dep in nodePositions && nodeId in nodePositions) {
        edges.push({
          from: dep,
          to: nodeId,
          is_critical: criticalSet.has(dep) && criticalSet.has(nodeId),
        });
      }
    }
  }

  // Calculate canvas size
  const maxX = Math.max(...positioned.map(n => n.x)) + NODE_W + 80;
  const maxY = Math.max(...positioned.map(n => n.y)) + NODE_H + 80;

  return { positioned, edges, nodePositions, canvasW: Math.max(1000, maxX), canvasH: Math.max(500, maxY) };
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DAGViewer() {
  const { planId } = usePlanContext();
  const { data: dag, error, isLoading } = useSWR<DAG>(planId ? `/plans/${planId}/dag` : null);
  const { progress } = useWarRoomProgress(planId);

  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Build status lookup from progress.json
  const statusMap = useMemo(() => {
    const map = new Map<string, string>();
    if (progress?.rooms) {
      for (const room of progress.rooms) {
        map.set(room.task_ref, room.status);
      }
    }
    return map;
  }, [progress]);

  const layout = useMemo(() => {
    if (!dag || !dag.nodes || !dag.waves) return null;
    return layoutDAG(dag, statusMap);
  }, [dag, statusMap]);

  const handleZoom = (delta: number) => {
    setScale(prev => Math.min(Math.max(prev + delta, 0.3), 2.5));
  };

  const handleFitToView = () => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
  };

  // ── Loading / Error states ──
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <span className="animate-spin material-symbols-outlined text-[32px] text-primary">progress_activity</span>
      </div>
    );
  }

  if (error || !dag || !layout) {
    return (
      <div className="flex-1 flex items-center justify-center h-full text-text-faint italic font-medium">
        Failed to load DAG or DAG not available for this plan.
      </div>
    );
  }

  const { positioned, edges, canvasW, canvasH } = layout;
  const criticalSet = new Set(dag.critical_path ?? []);

  // Filter edges based on critical-path toggle
  const filteredEdges = showCriticalOnly ? edges.filter(e => e.is_critical) : edges;
  // Filter nodes based on critical-path toggle
  const filteredNodes = showCriticalOnly
    ? positioned.filter(n => criticalSet.has(n.id))
    : positioned;

  return (
    <div className="relative w-full h-full bg-surface-alt/10 flex flex-col overflow-hidden">
      {/* ── Toolbar ── */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 p-1 bg-surface/80 backdrop-blur-sm border border-border rounded-lg shadow-sm">
        <button
          onClick={() => handleZoom(0.1)}
          className="p-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors"
          title="Zoom In"
        >
          <span className="material-symbols-outlined text-[18px]">add</span>
        </button>
        <button
          onClick={() => handleZoom(-0.1)}
          className="p-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors"
          title="Zoom Out"
        >
          <span className="material-symbols-outlined text-[18px]">remove</span>
        </button>
        <div className="w-[1px] h-4 bg-border mx-0.5" />
        <button
          onClick={handleFitToView}
          className="p-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors"
          title="Fit to View"
        >
          <span className="material-symbols-outlined text-[18px]">fit_screen</span>
        </button>
        <div className="w-[1px] h-4 bg-border mx-0.5" />
        <button
          onClick={() => setShowCriticalOnly(!showCriticalOnly)}
          className={`px-2 py-1 flex items-center gap-1.5 rounded-md text-[10px] font-bold uppercase transition-all ${
            showCriticalOnly
              ? 'bg-primary/10 text-primary border border-primary/20'
              : 'bg-surface-alt text-text-faint border border-transparent hover:bg-surface-hover'
          }`}
          title="Toggle Critical Path"
        >
          <span className="material-symbols-outlined text-[14px]">route</span>
          Critical Path
        </button>
      </div>

      {/* ── DAG Info badges ── */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
        <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-surface/80 border border-border text-text-faint backdrop-blur-sm">
          {dag.total_nodes} nodes
        </span>
        <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-surface/80 border border-border text-text-faint backdrop-blur-sm">
          depth {dag.max_depth}
        </span>
        <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-primary/10 border border-primary/20 text-primary backdrop-blur-sm">
          🔥 {dag.critical_path_length}-step critical
        </span>
        {progress && (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 backdrop-blur-sm">
            {progress.pct_complete}% complete
          </span>
        )}
      </div>

      {/* ── SVG Canvas ── */}
      <div
        ref={containerRef}
        className="flex-1 w-full h-full overflow-auto cursor-grab active:cursor-grabbing"
      >
        <svg
          width={canvasW * scale}
          height={canvasH * scale}
          viewBox={`0 0 ${canvasW} ${canvasH}`}
          xmlns="http://www.w3.org/2000/svg"
          className="min-w-full min-h-full"
        >
          <defs>
            <marker id="arrowhead-critical" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb" />
            </marker>
            <marker id="arrowhead-normal" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
            </marker>
          </defs>
          <g transform={`scale(${scale}) translate(${translate.x}, ${translate.y})`}>
            {/* Edges (behind nodes) */}
            {filteredEdges.map((edge, idx) => {
              const fromNode = positioned.find(n => n.id === edge.from);
              const toNode = positioned.find(n => n.id === edge.to);
              if (!fromNode || !toNode) return null;
              return (
                <DAGEdge
                  key={`edge-${idx}`}
                  edge={edge}
                  fromPos={{ x: fromNode.x, y: fromNode.y }}
                  toPos={{ x: toNode.x, y: toNode.y }}
                />
              );
            })}

            {/* Nodes */}
            {filteredNodes.map((node) => (
              <StateNode
                key={node.id}
                id={node.id}
                label={node.label}
                status={node.status as any}
                x={node.x}
                y={node.y}
                role={node.role}
                roleInitial={node.roleInitial}
                roleColor={node.roleColor}
              />
            ))}
          </g>
        </svg>
      </div>

      {/* ── Critical Path Strip ── */}
      {dag.critical_path && dag.critical_path.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-4 py-2 bg-surface border-t border-border">
          <span className="text-[10px] font-bold text-primary uppercase tracking-wider mr-1">🔥 Critical Path</span>
          {dag.critical_path.map((id, idx) => {
            const nodeStatus = statusMap.get(id);
            const statusColor = nodeStatus === 'passed' ? '#10b981' : nodeStatus === 'failed-final' ? '#ef4444' : nodeStatus === 'engineering' ? '#3b82f6' : '#94a3b8';
            return (
              <React.Fragment key={id}>
                <span 
                  className="px-2 py-0.5 text-[11px] font-semibold rounded border flex items-center gap-1"
                  style={{ background: `${statusColor}15`, color: statusColor, borderColor: `${statusColor}30` }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusColor }} />
                  {id}
                </span>
                {idx < dag.critical_path.length - 1 && (
                  <span className="text-[10px] text-text-faint">→</span>
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}
