'use client';

import { useState } from 'react';
import { Epic } from '@/types';
import EpicCard from './EpicCard';
import { stateColors } from './EpicCard';
import { useDroppable } from '@dnd-kit/core';

interface KanbanColumnProps {
  state: string;
  label: string;
  epics: Epic[];
  isOver?: boolean;
  isInvalid?: boolean;
  criticalPathSet?: Set<string>;
  warRoomStatusMap?: Map<string, string>;
  collapsed?: boolean;
}

export default function KanbanColumn({ state, label, epics, isOver, isInvalid, criticalPathSet, warRoomStatusMap, collapsed }: KanbanColumnProps) {
  const color = stateColors[state] || stateColors.pending;
  const { setNodeRef } = useDroppable({
    id: state,
  });
  const [hovered, setHovered] = useState(false);

  // Collapsed rendering: slim vertical pill for empty lifecycle columns
  if (collapsed && !isOver) {
    return (
      <div
        ref={setNodeRef}
        className="flex flex-col items-center shrink-0 h-full transition-all duration-300 group/col cursor-default"
        style={{ width: hovered ? '120px' : '48px' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div 
          className="flex flex-col items-center gap-2 py-3 px-1 rounded-xl border border-border/50 bg-surface/50 h-full w-full transition-all duration-300 hover:border-border hover:bg-surface"
        >
          <span 
            className="w-2.5 h-2.5 rounded-full shrink-0" 
            style={{ background: color }} 
          />
          <span 
            className="text-[9px] font-bold text-text-faint uppercase tracking-tight transition-all duration-300"
            style={{ 
              writingMode: hovered ? 'horizontal-tb' : 'vertical-rl',
              textOrientation: 'mixed',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </span>
          <span className="text-[9px] font-bold text-text-faint/50 mt-auto">0</span>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={setNodeRef}
      className={`flex flex-col min-w-[280px] max-w-[320px] h-full shrink-0 transition-all duration-200 relative rounded-xl border-2 ${
        isOver 
          ? isInvalid 
            ? 'border-red-500/50 bg-red-50/10' 
            : 'border-primary/50 bg-primary/5 shadow-lg scale-[1.02]'
          : 'border-transparent'
      }`}
    >
      {/* Column Header */}
      <div className="px-4 py-3 mb-2 flex items-center justify-between border-b-2" style={{ borderColor: color }}>
        <div className="flex items-center gap-2">
          <span 
            className="w-2.5 h-2.5 rounded-full" 
            style={{ background: color }} 
          />
          <h3 className="text-[12px] font-extrabold text-text-main uppercase tracking-tight">
            {label}
          </h3>
        </div>
        <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-surface border border-border text-text-muted">
          {epics.length}
        </span>
      </div>

      {/* Column Content */}
      <div 
        className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar rounded-b-xl"
        style={{ background: `${color}05` }}
      >
        {epics.length > 0 ? (
          epics.map((epic) => (
            <EpicCard 
              key={epic.epic_ref} 
              epic={epic}
              onCriticalPath={criticalPathSet?.has(epic.epic_ref)}
              warRoomStatus={warRoomStatusMap?.get(epic.epic_ref)}
            />
          ))
        ) : (
          <div className="flex flex-col items-center justify-center py-20 text-center opacity-30 select-none">
            <span className="material-symbols-outlined text-4xl mb-2 text-text-faint">
              drag_indicator
            </span>
            <p className="text-[10px] font-bold text-text-faint uppercase tracking-widest">
              No EPICs in this state
            </p>
          </div>
        )}
      </div>

      {/* Invalid Target Overlay */}
      {isOver && isInvalid && (
        <div className="absolute inset-0 bg-red-500/10 flex flex-col items-center justify-center pointer-events-none rounded-xl z-50">
          <div className="bg-red-500 text-white px-3 py-1.5 rounded-full flex items-center gap-2 shadow-lg animate-bounce">
            <span className="material-symbols-outlined text-sm">block</span>
            <span className="text-[10px] font-bold uppercase tracking-wider">Invalid Transition</span>
          </div>
        </div>
      )}
    </div>
  );
}
