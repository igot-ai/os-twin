'use client';

import React from 'react';
import { Epic } from '@/types';
import { usePlanContext } from './PlanWorkspace';
import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';

export const stateColors: Record<string, string> = {
  pending: '#94a3b8',
  engineering: '#3b82f6',
  'qa-review': '#8b5cf6',
  fixing: '#f59e0b',
  'manager-triage': '#ef4444',
  passed: '#10b981',
  signoff: '#10b981',
  'failed-final': '#ef4444',
};

const roleColors: Record<string, string> = {
  'Data Analyst': '#6366f1',
  'Copywriter': '#f59e0b',
  'Designer': '#ec4899',
  'Engineer': '#3b82f6',
  'Auditor': '#8b5cf6',
  'Manager': '#64748b',
};

export default function EpicCard({ epic }: { epic: Epic }) {
  const { selectedEpicRef, setSelectedEpicRef, setIsContextPanelOpen } = usePlanContext();
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: epic.epic_ref,
  });

  const style = transform ? {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.3 : undefined,
    zIndex: isDragging ? 100 : undefined,
  } : undefined;
  
  const isSelected = selectedEpicRef === epic.epic_ref;
  const stateColor = stateColors[epic.lifecycle_state || 'pending'] || stateColors.pending;
  const roleColor = roleColors[epic.role || ''] || '#6366f1';

  const handleClick = () => {
    setSelectedEpicRef(epic.epic_ref);
    setIsContextPanelOpen(true);
  };

  const completedTasks = (epic.tasks || []).filter(t => t.completed).length;
  const totalTasks = (epic.tasks || []).length;
  const progressPercent = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

  return (
    <div
      ref={setNodeRef}
      onClick={handleClick}
      className={`group relative p-3 rounded-lg border bg-surface transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md hover:-translate-y-0.5 ${
        isSelected ? 'border-primary ring-1 ring-primary/20 shadow-md' : 'border-border hover:border-text-faint'
      }`}
      style={{ ...style, borderLeftWidth: '3px', borderLeftColor: stateColor }}
      role="button"
      aria-pressed={isSelected}
      aria-label={`Epic ${epic.epic_ref}: ${epic.title}`}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
    >
      {/* Drag Handle */}
      <div 
        {...attributes} 
        {...listeners} 
        className="absolute -left-1 top-1/2 -translate-y-1/2 w-4 h-8 flex items-center justify-center opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing transition-opacity z-20"
        aria-label="Drag to reorder epic"
        role="button"
      >
        <span className="material-symbols-outlined text-xs text-text-faint" aria-hidden="true">drag_indicator</span>
      </div>

      {/* Ref & State Badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] font-bold text-text-faint tracking-wider uppercase">
          {epic.epic_ref}
        </span>
        <div 
          className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold uppercase"
          style={{ background: `${stateColor}15`, color: stateColor }}
        >
          <span className={`w-1 h-1 rounded-full ${(epic.lifecycle_state || 'pending') !== 'passed' && (epic.lifecycle_state || 'pending') !== 'signoff' ? 'animate-pulse' : ''}`} style={{ background: stateColor }} />
          {(epic.lifecycle_state || 'pending').replace('-', ' ')}
        </div>
      </div>

      {/* Title */}
      <h4 className="text-[12px] font-bold text-text-main line-clamp-2 leading-tight mb-3 group-hover:text-primary transition-colors h-8">
        {epic.title}
      </h4>

      {/* Progress Bar */}
      <div className="space-y-1 mb-3">
        <div className="flex justify-between text-[9px] font-bold text-text-faint uppercase">
          <span>Progress</span>
          <span>{Math.round(progressPercent)}%</span>
        </div>
        <div className="h-1 w-full bg-border/50 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ${progressPercent === 100 ? 'bg-success' : 'bg-primary'}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Footer: Role & Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <div 
            className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-white shadow-inner shrink-0"
            style={{ background: roleColor }}
            title={epic.role || 'Unassigned'}
          >
            {(epic.role || '??').split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2)}
          </div>
          <span className="text-[10px] font-medium text-text-muted truncate">{epic.role || 'Unassigned'}</span>
        </div>
        
        {/* Task Count indicator */}
        <div className="flex items-center gap-0.5 text-text-faint ml-2 shrink-0">
          <span className="material-symbols-outlined text-[12px]">checklist</span>
          <span className="text-[10px] font-bold">{completedTasks}/{totalTasks}</span>
        </div>
      </div>
    </div>
  );
}
