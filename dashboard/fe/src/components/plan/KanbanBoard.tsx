'use client';

import React, { useMemo, useState } from 'react';
import { usePlanContext } from './PlanWorkspace';
import KanbanColumn from './KanbanColumn';
import EpicCard from './EpicCard';
import { Epic, EpicStatus } from '@/types';
import { useDAG } from '@/hooks/use-epics';
import { useWarRoomProgress } from '@/hooks/use-war-room';
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core';

const stateMapping = [
  { state: 'pending', label: 'Pending' },
  { state: 'engineering', label: 'Engineering' },
  { state: 'qa-review', label: 'QA Review' },
  { state: 'fixing', label: 'Fixing' },
  { state: 'manager-triage', label: 'Triage' },
  { state: 'passed', label: 'Passed' },
  { state: 'signoff', label: 'Signoff' },
  { state: 'failed-final', label: 'Failed' },
];

// Valid transitions: roughly linear, but allow backtracking to engineering/fixing
const validTransitions: Record<string, string[]> = {
  pending: ['engineering'],
  engineering: ['qa-review', 'fixing'],
  'qa-review': ['passed', 'fixing', 'manager-triage'],
  fixing: ['qa-review'],
  'manager-triage': ['engineering', 'fixing', 'failed-final'],
  passed: ['signoff', 'fixing'],
  signoff: [],
  'failed-final': [],
};

export default function KanbanBoard() {
  const { epics, isLoading, updateEpicState, planId } = usePlanContext();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overState, setOverState] = useState<string | null>(null);

  // Fetch DAG and progress for enrichment
  const { dag } = useDAG(planId);
  const { progress } = useWarRoomProgress(planId);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // Build lookup maps from DAG and progress data
  const criticalPathSet = useMemo(() => {
    if (!dag?.critical_path) return new Set<string>();
    return new Set(dag.critical_path);
  }, [dag]);

  const warRoomStatusMap = useMemo(() => {
    if (!progress?.rooms) return new Map<string, string>();
    const map = new Map<string, string>();
    for (const room of progress.rooms) {
      map.set(room.task_ref, room.status);
    }
    return map;
  }, [progress]);

  const groupedEpics = useMemo(() => {
    if (!epics) return {} as Record<string, Epic[]>;
    
    return epics.reduce((acc, epic) => {
      const state = epic.lifecycle_state || 'pending';
      if (!acc[state]) acc[state] = [];
      acc[state].push(epic);
      return acc;
    }, {} as Record<string, Epic[]>);
  }, [epics]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { over } = event;
    if (over) {
      setOverState(over.id as string);
    } else {
      setOverState(null);
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);
    setOverState(null);

    if (over && epics) {
      const epicRef = active.id as string;
      const newState = over.id as string;
      const epic = epics.find(e => e.epic_ref === epicRef);

      if (epic && (epic.lifecycle_state || 'pending') !== newState) {
        // Validate transition
        const allowed = validTransitions[epic.lifecycle_state || 'pending'] || [];
        if (allowed.includes(newState) || newState === (epic.lifecycle_state || 'pending')) {
          try {
            await updateEpicState(epicRef, newState, newState as EpicStatus);
          } catch (err) {
            console.error('Failed to move epic:', err);
          }
        }
      }
    }
  };

  if (isLoading && !epics) {
    return (
      <div className="h-full flex flex-col p-6 overflow-hidden">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-border rounded-lg" />
          <div className="flex gap-6 overflow-x-auto pb-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="min-w-[280px] h-[600px] bg-border/20 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const activeEpic = activeId ? epics?.find(e => e.epic_ref === activeId) : null;

  // Count summary stats
  const passedCount = epics?.filter(e => (e.lifecycle_state || 'pending') === 'passed' || (e.lifecycle_state || 'pending') === 'signoff').length || 0;
  const failedCount = epics?.filter(e => (e.lifecycle_state || 'pending') === 'failed-final').length || 0;
  const activeCount = epics?.filter(e => !['pending', 'passed', 'signoff', 'failed-final'].includes(e.lifecycle_state || 'pending')).length || 0;

  return (
    <div className="h-full flex flex-col p-6 overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-extrabold text-text-main">
            EPIC Lifecycle
          </h2>
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-surface border border-border text-text-muted shadow-sm">
            {epics?.length || 0} TOTAL
          </span>
          {/* Status summary chips */}
          {passedCount > 0 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
              ✓ {passedCount} passed
            </span>
          )}
          {activeCount > 0 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 border border-blue-500/20">
              ⚡ {activeCount} active
            </span>
          )}
          {failedCount > 0 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500/10 text-red-600 border border-red-500/20">
              ✕ {failedCount} failed
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {/* Progress from progress.json */}
          {progress && (
            <span className="text-[10px] font-bold text-text-muted bg-surface-hover px-2 py-1 rounded-md border border-border">
              {progress.pct_complete}% • CP {progress.critical_path}
            </span>
          )}
          <div className="flex -space-x-1 hover:space-x-1 transition-all">
            <button className="p-1.5 rounded-md border border-border bg-surface text-text-faint hover:text-text-main hover:bg-surface-hover transition-colors shadow-sm">
              <span className="material-symbols-outlined text-[18px]">search</span>
            </button>
            <button className="p-1.5 rounded-md border border-border bg-surface text-text-faint hover:text-text-main hover:bg-surface-hover transition-colors shadow-sm">
              <span className="material-symbols-outlined text-[18px]">tune</span>
            </button>
          </div>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="flex-1 flex gap-6 overflow-x-auto custom-scrollbar pb-6 min-h-0 select-none">
          {stateMapping.map((item) => {
            return (
              <KanbanColumn 
                key={item.state} 
                state={item.state} 
                label={item.label} 
                epics={groupedEpics[item.state] || []}
                isOver={overState === item.state}
                isInvalid={isOverStateInvalid(activeEpic, item.state)}
                criticalPathSet={criticalPathSet}
                warRoomStatusMap={warRoomStatusMap}
              />
            );
          })}
          {/* Spacer for overflow end padding */}
          <div className="min-w-[1px] shrink-0" />
        </div>

        <DragOverlay dropAnimation={{
          sideEffects: defaultDropAnimationSideEffects({
            styles: {
              active: {
                opacity: '0.5',
              },
            },
          }),
        }}>
          {activeEpic ? (
            <div className="w-[280px] rotate-3 cursor-grabbing">
              <EpicCard 
                epic={activeEpic} 
                onCriticalPath={criticalPathSet.has(activeEpic.epic_ref)}
                warRoomStatus={warRoomStatusMap.get(activeEpic.epic_ref)}
              />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

function isOverStateInvalid(activeEpic: Epic | null | undefined, overState: string) {
  if (!activeEpic) return false;
  if ((activeEpic.lifecycle_state || 'pending') === overState) return false;
  const allowed = validTransitions[activeEpic.lifecycle_state || 'pending'] || [];
  return !allowed.includes(overState);
}
