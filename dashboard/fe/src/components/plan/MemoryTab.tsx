'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { apiGet } from '@/lib/api-client';

// ── Types ────────────────────────────────────────────────────────────

interface MemoryNote {
  id: string;
  title: string;
  path: string;
  relativePath: string;
  excerpt: string;
  content?: string;
  tags: string[];
  keywords: string[];
  links: string[];
}

interface GraphGroup {
  id: string;
  label: string;
  color: string;
  description: string;
}

interface GraphNode {
  id: string;
  title: string;
  path: string;
  pathLabel: string;
  excerpt: string;
  content: string;
  tags: string[];
  keywords: string[];
  groupId: string;
  color: string;
  weight: number;
  connections: number;
  // computed by layout
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  strength: number;
}

interface GraphData {
  groups: GraphGroup[];
  nodes: GraphNode[];
  links: GraphLink[];
  stats: { total_memories: number; total_links: number; total_groups: number };
}

interface MemoryStats {
  total_notes: number;
  total_tags: number;
  total_keywords: number;
  total_paths: number;
  memory_dir: string;
  tags: string[];
  paths: string[];
}

// ── Simple force layout ──────────────────────────────────────────────

function layoutNodes(nodes: GraphNode[], links: GraphLink[], width: number, height: number): GraphNode[] {
  const positioned = nodes.map((n, i) => ({
    ...n,
    x: width / 2 + (Math.cos(i * 2.399) * Math.min(width, height) * 0.35),
    y: height / 2 + (Math.sin(i * 2.399) * Math.min(width, height) * 0.35),
  }));

  // Simple force iterations
  const nodeMap = new Map(positioned.map(n => [n.id, n]));
  for (let iter = 0; iter < 50; iter++) {
    // Repel
    for (let i = 0; i < positioned.length; i++) {
      for (let j = i + 1; j < positioned.length; j++) {
        const a = positioned[i], b = positioned[j];
        const dx = b.x! - a.x!, dy = b.y! - a.y!;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = 800 / (dist * dist);
        a.x! -= (dx / dist) * force;
        a.y! -= (dy / dist) * force;
        b.x! += (dx / dist) * force;
        b.y! += (dy / dist) * force;
      }
    }
    // Attract linked
    for (const link of links) {
      const a = nodeMap.get(link.source), b = nodeMap.get(link.target);
      if (!a || !b) continue;
      const dx = b.x! - a.x!, dy = b.y! - a.y!;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const force = (dist - 120) * 0.02;
      a.x! += (dx / dist) * force;
      a.y! += (dy / dist) * force;
      b.x! -= (dx / dist) * force;
      b.y! -= (dy / dist) * force;
    }
    // Center
    for (const n of positioned) {
      n.x! += (width / 2 - n.x!) * 0.01;
      n.y! += (height / 2 - n.y!) * 0.01;
    }
  }
  return positioned;
}

// ── Graph SVG ────────────────────────────────────────────────────────

function MemoryGraph({
  data,
  selectedId,
  onSelect,
}: {
  data: GraphData;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (el) {
      const obs = new ResizeObserver(entries => {
        const { width, height } = entries[0].contentRect;
        setDimensions({ width: Math.max(400, width), height: Math.max(300, height) });
      });
      obs.observe(el);
      return () => obs.disconnect();
    }
  }, []);

  const nodes = layoutNodes(data.nodes, data.links, dimensions.width, dimensions.height);
  const nodeMap = new Map(nodes.map(n => [n.id, n]));

  // Find neighbors of selected node
  const neighborIds = new Set<string>();
  if (selectedId) {
    for (const link of data.links) {
      if (link.source === selectedId) neighborIds.add(link.target);
      if (link.target === selectedId) neighborIds.add(link.source);
    }
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
      className="w-full h-full"
      style={{ minHeight: 400 }}
    >
      {/* Links */}
      {data.links.map((link, i) => {
        const src = nodeMap.get(link.source);
        const tgt = nodeMap.get(link.target);
        if (!src || !tgt) return null;
        const isActive = selectedId && (link.source === selectedId || link.target === selectedId);
        return (
          <line
            key={i}
            x1={src.x} y1={src.y}
            x2={tgt.x} y2={tgt.y}
            stroke={isActive ? 'var(--color-primary)' : 'var(--color-border)'}
            strokeWidth={isActive ? 2 : 1}
            opacity={isActive ? 0.8 : 0.3}
          />
        );
      })}
      {/* Nodes */}
      {nodes.map(node => {
        const isSelected = node.id === selectedId;
        const isNeighbor = neighborIds.has(node.id);
        const r = 6 + node.weight * 3;
        return (
          <g key={node.id} onClick={() => onSelect(node.id)} style={{ cursor: 'pointer' }}>
            {isSelected && (
              <circle cx={node.x} cy={node.y} r={r + 6} fill="none"
                stroke="var(--color-primary)" strokeWidth={2} opacity={0.5} />
            )}
            <circle
              cx={node.x} cy={node.y} r={r}
              fill={node.color}
              opacity={isSelected ? 1 : isNeighbor ? 0.85 : 0.6}
              stroke={isSelected ? '#fff' : 'none'}
              strokeWidth={isSelected ? 2 : 0}
            />
            <text
              x={node.x} y={node.y! + r + 14}
              textAnchor="middle"
              fontSize={11}
              fill="var(--color-text-main)"
              opacity={isSelected || isNeighbor ? 1 : 0.5}
              style={{ pointerEvents: 'none' }}
            >
              {node.title.length > 24 ? node.title.slice(0, 22) + '...' : node.title}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Note detail panel ────────────────────────────────────────────────

function NoteDetail({ note }: { note: GraphNode | null }) {
  if (!note) {
    return (
      <div className="p-6 text-center" style={{ color: 'var(--color-text-muted)' }}>
        <span className="material-symbols-outlined text-[40px] mb-3 block opacity-40">psychology</span>
        <p className="text-sm">Select a memory node to view details</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div>
        <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
          {note.title}
        </h3>
        <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
          {note.pathLabel}
        </p>
      </div>

      {note.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {note.tags.map(tag => (
            <span
              key={tag}
              className="px-2 py-0.5 rounded-full text-[10px] font-medium"
              style={{
                background: 'var(--color-primary-muted)',
                color: 'var(--color-primary)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div
        className="text-sm leading-relaxed whitespace-pre-wrap"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {note.excerpt || note.content}
      </div>

      {note.keywords.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest mb-1.5"
            style={{ color: 'var(--color-text-muted)' }}>
            Keywords
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {note.keywords.join(', ')}
          </p>
        </div>
      )}

      <div className="flex gap-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <span>{note.connections} connections</span>
        <span>{note.groupId}</span>
      </div>
    </div>
  );
}

// ── Main MemoryTab ───────────────────────────────────────────────────

export default function MemoryTab() {
  const { planId } = usePlanContext();
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchData = useCallback(async () => {
    if (!planId) return;
    setLoading(true);
    setError(null);
    try {
      const [graph, st] = await Promise.all([
        apiGet<GraphData>(`/api/amem/${planId}/graph`),
        apiGet<MemoryStats>(`/api/amem/${planId}/stats`),
      ]);
      setGraphData(graph);
      setStats(st);
      if (graph.nodes.length > 0 && !selectedNodeId) {
        setSelectedNodeId(graph.nodes[0].id);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load memory data');
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const selectedNode = graphData?.nodes.find(n => n.id === selectedNodeId) || null;

  // Filter nodes by search
  const filteredNodes = graphData?.nodes.filter(n => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return n.title.toLowerCase().includes(q) ||
      n.pathLabel.toLowerCase().includes(q) ||
      n.tags.some(t => t.toLowerCase().includes(q)) ||
      n.excerpt.toLowerCase().includes(q);
  }) || [];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading memory graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3 max-w-md">
          <span className="material-symbols-outlined text-[48px]" style={{ color: 'var(--color-text-muted)' }}>
            memory
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            No memories found
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {error}
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Run the plan to generate agent memories, or check that .memory/ exists in the project directory.
          </p>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3 max-w-md">
          <span className="material-symbols-outlined text-[48px]" style={{ color: 'var(--color-text-muted)' }}>
            psychology
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            No memories yet
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Agent memories will appear here after running the plan. Each save_memory() call creates a node.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-hidden">
      {/* Stats bar */}
      <div className="flex items-center justify-between gap-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-[20px]" style={{ color: 'var(--color-primary)' }}>
            psychology
          </span>
          <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
            Agent Memory
          </h2>
          {stats && (
            <div className="flex gap-2">
              <span className="px-2 py-0.5 rounded-md text-[11px] font-medium"
                style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}>
                {stats.total_notes} notes
              </span>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-medium"
                style={{ background: 'var(--color-background-alt)', color: 'var(--color-text-secondary)' }}>
                {stats.total_tags} tags
              </span>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-medium"
                style={{ background: 'var(--color-background-alt)', color: 'var(--color-text-secondary)' }}>
                {graphData.links.length} links
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <span className="material-symbols-outlined text-[16px] absolute left-2.5 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--color-text-muted)' }}>
              search
            </span>
            <input
              className="pl-8 pr-3 py-1.5 text-xs rounded-lg border"
              style={{
                background: 'var(--color-background)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-main)',
                width: 200,
              }}
              placeholder="Search memories..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            onClick={fetchData}
            className="p-1.5 rounded-lg border transition-colors hover:bg-[var(--color-background-alt)]"
            style={{ borderColor: 'var(--color-border)' }}
            title="Refresh"
          >
            <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-text-muted)' }}>
              refresh
            </span>
          </button>
        </div>
      </div>

      {/* Main content: graph + sidebar */}
      <div className="flex-1 flex gap-4 overflow-hidden min-h-0">
        {/* Left: note list */}
        <div className="w-56 flex-shrink-0 flex flex-col gap-2 overflow-y-auto"
          style={{ scrollbarWidth: 'thin' }}>
          {/* Groups legend */}
          <div className="space-y-1 mb-2">
            {graphData.groups.map(g => (
              <div key={g.id} className="flex items-center gap-2 px-2 py-1">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: g.color }} />
                <span className="text-[11px] truncate" style={{ color: 'var(--color-text-secondary)' }}>
                  {g.label}
                </span>
              </div>
            ))}
          </div>

          {/* Note list */}
          {filteredNodes.map(node => (
            <button
              key={node.id}
              className="w-full text-left px-3 py-2.5 rounded-xl border transition-all"
              style={{
                borderColor: selectedNodeId === node.id ? 'var(--color-primary)' : 'var(--color-border)',
                background: selectedNodeId === node.id ? 'var(--color-primary-muted)' : 'transparent',
              }}
              onClick={() => setSelectedNodeId(node.id)}
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: node.color }} />
                <span className="text-xs font-medium truncate" style={{ color: 'var(--color-text-main)' }}>
                  {node.title}
                </span>
              </div>
              <p className="text-[10px] mt-0.5 truncate ml-4" style={{ color: 'var(--color-text-muted)' }}>
                {node.pathLabel}
              </p>
            </button>
          ))}
        </div>

        {/* Center: graph */}
        <div className="flex-1 rounded-2xl border overflow-hidden"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-background)' }}>
          <MemoryGraph
            data={graphData}
            selectedId={selectedNodeId}
            onSelect={setSelectedNodeId}
          />
        </div>

        {/* Right: detail panel */}
        <div className="w-72 flex-shrink-0 rounded-2xl border overflow-y-auto"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-background-alt)' }}>
          <NoteDetail note={selectedNode} />
        </div>
      </div>
    </div>
  );
}
