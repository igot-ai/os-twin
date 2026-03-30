'use client';

import React, { useState, useRef, useMemo } from 'react';
import useSWR from 'swr';
import { usePlanContext } from './PlanWorkspace';
import { DAG, DAGNodeRaw } from '@/types';
import { useWarRoomProgress } from '@/hooks/use-war-room';
import { roleColorMap, getRoleColor, getRoleInitial } from '@/lib/role-utils';
import { deriveDAGFromDocument, wouldCreateCycle } from '@/lib/dag-layout';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import { EpicDetailDrawer } from './EpicDetailDrawer';
import StateNode from './StateNode';
import DAGEdge from './DAGEdge';

// ─── Drag state type ──────────────────────────────────────────────────────────

type DragState =
  | { type: 'idle' }
  | { type: 'dragging'; sourceRef: string; cursorX: number; cursorY: number; targetRef?: string; isValid?: boolean };

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
        roleInitial: getRoleInitial(role),
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

export interface DAGViewerProps {
  mode?: 'live' | 'authoring';
}

export default function DAGViewer({ mode: modeProp }: DAGViewerProps) {
  const { 
    planId, parsedPlan, updateParsedPlan, 
    setSelectedEpicRef, setIsContextPanelOpen, setActiveTab,
    undo, redo, canUndo, canRedo, savePlan
  } = usePlanContext();
  const addToast = useNotificationStore(state => state.addToast);
  const { data: serverDag, error, isLoading: isServerLoading } = useSWR<DAG>(planId ? `/plans/${planId}/dag` : null);
  const { progress } = useWarRoomProgress(planId);

  const derivedDAG = useMemo(() => {
    if (!parsedPlan) return null;
    return deriveDAGFromDocument(parsedPlan);
  }, [parsedPlan]);

  const mode = modeProp || (progress?.rooms?.length ? 'live' : 'authoring');
  const dag = mode === 'live' ? serverDag : derivedDAG;
  const isLoading = mode === 'live' ? isServerLoading : !dag;

  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [dragState, setDragState] = useState<DragState>({ type: 'idle' });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpicRef, setEditingEpicRef] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number, y: number, ref: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
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

  const { nodePositions } = layout || {};

  const editingEpic = useMemo(() => {
    if (!editingEpicRef || !parsedPlan) return null;
    return parsedPlan.epics.find(e => e.ref === editingEpicRef) || null;
  }, [editingEpicRef, parsedPlan]);

  const handleNodeClick = (ref: string) => {
    if (mode === 'authoring') {
      setEditingEpicRef(ref);
      setIsDrawerOpen(true);
    } else {
      setSelectedEpicRef(ref);
      setIsContextPanelOpen(true);
    }
  };

  const handleContextMenu = (e: React.MouseEvent, ref: string) => {
    if (mode === 'authoring') {
      e.preventDefault();
      setContextMenu({ x: e.clientX, y: e.clientY, ref });
    }
  };

  const handleDuplicateEpic = (ref: string) => {
    updateParsedPlan((doc) => {
      const source = doc.epics.find(e => e.ref === ref);
      if (source) {
        // Find next ref
        const refs = doc.epics.map(e => {
            const match = e.ref.match(/EPIC-(\d+)/);
            return match ? parseInt(match[1]) : 0;
        });
        const nextNum = Math.max(0, ...refs) + 1;
        const nextRef = `EPIC-${nextNum.toString().padStart(3, '0')}`;
        
        // Proper deep copy of EpicNode, handling Map
        const newEpic = {
          ...JSON.parse(JSON.stringify(source)),
          frontmatter: new Map(source.frontmatter)
        };
        newEpic.ref = nextRef;
        newEpic.depends_on = [];
        const prefix = newEpic.headingLevel === 3 ? '###' : '##';
        newEpic.title = `${source.title} (Copy)`;
        newEpic.rawHeading = `${prefix} ${nextRef} — ${newEpic.title}`;
        
        doc.epics.push(newEpic);
        addToast({
          type: 'success',
          title: 'EPIC Duplicated',
          message: `Created ${nextRef}`
        });
      }
      return doc;
    });
    setContextMenu(null);
  };

  const handleDeleteEpic = (ref: string) => {
    if (window.confirm(`Are you sure you want to delete ${ref}?`)) {
      updateParsedPlan((doc) => {
        const newDoc = { ...doc };
        newDoc.epics = newDoc.epics.filter(e => e.ref !== ref);
        newDoc.epics.forEach(e => e.depends_on = e.depends_on.filter(d => d !== ref));
        return newDoc;
      });
      addToast({
        type: 'success',
        title: 'EPIC Deleted',
        message: `${ref} has been removed`
      });
    }
    setContextMenu(null);
  };

  const getCanvasCoords = (clientX: number, clientY: number) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    // transform: scale(S) translate(TX, TY)
    // x_screen = S * (x_canvas + TX) + rect.left
    // x_canvas = (x_screen - rect.left) / S - TX
    const x = (clientX - rect.left) / scale - translate.x;
    const y = (clientY - rect.top) / scale - translate.y;
    return { x, y };
  };

  const handleStartDrag = (nodeId: string, clientX: number, clientY: number) => {
    setDragState({ type: 'dragging', sourceRef: nodeId, cursorX: clientX, cursorY: clientY });
  };

  const handleEnterPort = (nodeId: string, type: 'input' | 'output') => {
    if (dragState.type === 'dragging' && type === 'input') {
      const isValid = nodeId !== dragState.sourceRef && !wouldCreateCycle(parsedPlan!, dragState.sourceRef, nodeId);
      setDragState(prev => ({ ...prev, targetRef: nodeId, isValid }));
      if (dragState.sourceRef !== nodeId && !isValid) {
        addToast({
          type: 'warning',
          title: 'Invalid Connection',
          message: 'This would create a circular dependency'
        });
      }
    }
  };

  const handleLeavePort = () => {
    if (dragState.type === 'dragging') {
      setDragState(prev => ({ ...prev, targetRef: undefined, isValid: undefined }));
    }
  };

  const handleConnect = (sourceRef: string, targetRef: string) => {
    if (!parsedPlan) return;
    
    updateParsedPlan((doc) => {
      const targetEpic = doc.epics.find(e => e.ref === targetRef);
      if (targetEpic) {
        if (!targetEpic.depends_on.includes(sourceRef)) {
          targetEpic.depends_on = [...targetEpic.depends_on, sourceRef];
        }
      }
      return doc;
    });
    addToast({
      type: 'success',
      title: 'Dependency Added',
      message: `${sourceRef} → ${targetRef}`
    });
  };

  const handleDeleteDependency = (from: string, to: string) => {
    if (!parsedPlan) return;
    updateParsedPlan((doc) => {
      const targetEpic = doc.epics.find(e => e.ref === to);
      if (targetEpic) {
        targetEpic.depends_on = targetEpic.depends_on.filter(ref => ref !== from);
      }
      return doc;
    });
    addToast({
      type: 'success',
      title: 'Dependency Removed',
      message: `${from} → ${to}`
    });
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (dragState.type === 'dragging') {
      setDragState(prev => ({ ...prev, cursorX: e.clientX, cursorY: e.clientY }));
    }
  };

  const onMouseUp = () => {
    if (dragState.type === 'dragging') {
      if (dragState.targetRef && dragState.isValid) {
        handleConnect(dragState.sourceRef, dragState.targetRef);
      }
      setDragState({ type: 'idle' });
    }
  };

  const handleZoom = (delta: number) => {
    setScale(prev => Math.min(Math.max(prev + delta, 0.3), 2.5));
  };

  const handleFitToView = () => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await savePlan();
    } catch (err) {
      addToast({
        type: 'error',
        title: 'Save Failed',
        message: 'Could not persist changes to disk'
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddEpic = () => {
    updateParsedPlan((doc) => {
      const refs = doc.epics.map(e => {
        const match = e.ref.match(/EPIC-(\d+)/);
        return match ? parseInt(match[1]) : 0;
      });
      const nextNum = Math.max(0, ...refs) + 1;
      const nextRef = `EPIC-${nextNum.toString().padStart(3, '0')}`;
      
      const newEpic = {
        ref: nextRef,
        title: 'New EPIC',
        headingLevel: 2,
        rawHeading: `## ${nextRef} — New EPIC`,
        frontmatter: new Map([['Owner', 'engineer'], ['Priority', 'P1']]),
        sections: [
          {
            heading: 'Description',
            headingLevel: 3,
            type: 'text' as const,
            content: 'Describe the high-level goal of this EPIC.',
            rawLines: ['Describe the high-level goal of this EPIC.'],
            preamble: [],
            postamble: []
          },
          {
            heading: 'Definition of Done',
            headingLevel: 3,
            type: 'checklist' as const,
            content: '',
            items: [{ text: 'Placeholder item', checked: false, rawLine: '- [ ] Placeholder item', prefix: '- [ ] ' }],
            rawLines: ['- [ ] Placeholder item'],
            preamble: [],
            postamble: []
          },
          {
            heading: 'Tasks',
            headingLevel: 3,
            type: 'tasklist' as const,
            content: '',
            tasks: [{ 
              id: `${nextRef}.1`, 
              title: 'Initial task', 
              completed: false, 
              body: '', 
              bodyLines: [], 
              rawHeader: `- [ ] **${nextRef}.1** — Initial task`,
              prefix: '- [ ] ',
              idPrefix: '**',
              idSuffix: '**',
              delimiter: ' — '
            }],
            rawLines: [`- [ ] **${nextRef}.1** — Initial task`],
            preamble: [],
            postamble: []
          }
        ],
        depends_on: [],
        rawDependsOn: 'depends_on: []'
      };
      
      doc.epics.push(newEpic);
      setEditingEpicRef(nextRef);
      setIsDrawerOpen(true);
      addToast({
        type: 'success',
        title: 'EPIC Created',
        message: `New node ${nextRef} added`
      });
    });
  };

  // ── Loading / Error states ──
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <span className="animate-spin material-symbols-outlined text-[32px] text-primary">progress_activity</span>
      </div>
    );
  }

  if ((error && mode === 'live') || !dag || !layout) {
    return (
      <div className="flex-1 flex items-center justify-center h-full text-text-faint italic font-medium">
        {mode === 'live' ? 'Failed to load DAG or DAG not available for this plan.' : 'Parsing plan document...'}
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
        <div className="flex items-center gap-1.5 px-2 py-1 mr-1 border-r border-border">
          <span className={`w-2 h-2 rounded-full ${mode === 'live' ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
          <span className="text-[10px] font-bold uppercase tracking-widest text-text-main">
            {mode === 'live' ? 'Live Mode' : 'Authoring'}
          </span>
        </div>

        {mode === 'authoring' && (
          <>
            <button
              onClick={handleAddEpic}
              className="px-2 py-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors flex items-center gap-1.5"
              title="Add EPIC"
            >
              <span className="material-symbols-outlined text-[18px]">add_box</span>
              <span className="text-[10px] font-bold uppercase">Add EPIC</span>
            </button>
            <div className="w-[1px] h-4 bg-border mx-0.5" />
            <button
              onClick={undo}
              disabled={!canUndo}
              className="p-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors disabled:opacity-30"
              title="Undo (Ctrl+Z)"
            >
              <span className="material-symbols-outlined text-[18px]">undo</span>
            </button>
            <button
              onClick={redo}
              disabled={!canRedo}
              className="p-1.5 hover:bg-surface-hover rounded-md text-text-main transition-colors disabled:opacity-30"
              title="Redo (Ctrl+Shift+Z)"
            >
              <span className="material-symbols-outlined text-[18px]">redo</span>
            </button>
            <div className="w-[1px] h-4 bg-border mx-0.5" />
          </>
        )}

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

        {mode === 'authoring' && (
          <>
            <div className="w-[1px] h-4 bg-border mx-0.5" />
            <button
              onClick={handleSave}
              disabled={isSaving}
              className={`px-2 py-1 flex items-center gap-1.5 rounded-md text-[10px] font-bold uppercase transition-all bg-primary text-white hover:opacity-90 disabled:opacity-50`}
              title="Save Plan"
            >
              <span className="material-symbols-outlined text-[14px]">{isSaving ? 'sync' : 'save'}</span>
              {isSaving ? 'Saving...' : 'Save'}
            </button>
          </>
        )}
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
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
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
                  mode={mode}
                  onDelete={handleDeleteDependency}
                />
              );
            })}

            {/* Ghost edge during drag */}
            {dragState.type === 'dragging' && nodePositions && (
              <line
                x1={nodePositions[dragState.sourceRef].x + NODE_W}
                y1={nodePositions[dragState.sourceRef].y + NODE_H / 2}
                x2={(dragState.cursorX - (containerRef.current?.getBoundingClientRect().left || 0)) / scale - translate.x}
                y2={(dragState.cursorY - (containerRef.current?.getBoundingClientRect().top || 0)) / scale - translate.y}
                stroke={dragState.targetRef ? (dragState.isValid ? "#10b981" : "#ef4444") : "#6366f1"}
                strokeWidth={2}
                strokeDasharray="5,5"
                markerEnd="url(#arrowhead-normal)"
              />
            )}

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
                mode={mode}
                onStartDrag={handleStartDrag}
                onEnterPort={handleEnterPort}
                onLeavePort={handleLeavePort}
                onClick={handleNodeClick}
                onContextMenu={handleContextMenu}
              />
            ))}
          </g>
        </svg>
      </div>

      {/* ── Context Menu ── */}
      {contextMenu && (
        <>
          <div 
            className="fixed inset-0 z-[110]" 
            onClick={() => setContextMenu(null)}
            onContextMenu={(e) => { e.preventDefault(); setContextMenu(null); }}
          />
          <div 
            className="fixed z-[111] bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[160px] animate-in fade-in zoom-in duration-100"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button 
              onClick={() => { setEditingEpicRef(contextMenu.ref); setIsDrawerOpen(true); setContextMenu(null); }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-main hover:bg-surface-alt transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">edit</span>
              Edit EPIC
            </button>
            <button 
              onClick={() => handleDuplicateEpic(contextMenu.ref)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-main hover:bg-surface-alt transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">content_copy</span>
              Duplicate
            </button>
            <button 
              onClick={() => { setActiveTab('editor'); setContextMenu(null); }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-main hover:bg-surface-alt transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">code</span>
              View Source
            </button>
            <div className="h-[1px] bg-border my-1" />
            <button 
              onClick={() => handleDeleteEpic(contextMenu.ref)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">delete</span>
              Delete
            </button>
          </div>
        </>
      )}

      <EpicDetailDrawer
        epic={editingEpic}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />

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
