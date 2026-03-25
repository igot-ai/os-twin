'use client';

import React from 'react';
import { EpicStatus } from '@/types';
import { usePlanContext } from './PlanWorkspace';
import { stateColors } from './EpicCard';

interface StateNodeProps {
  id: string;
  label: string;
  status: EpicStatus;
  x: number;
  y: number;
  role?: string;
  roleInitial?: string;
  roleColor?: string;
}

const statusLabels: Record<string, string> = {
  passed: 'PASSED',
  'failed-final': 'FAILED',
  engineering: 'ENGINEERING',
  pending: 'PENDING',
  active: 'ACTIVE',
  blocked: 'BLOCKED',
  'qa-review': 'QA REVIEW',
  fixing: 'FIXING',
  'manager-triage': 'TRIAGE',
  signoff: 'SIGNOFF',
};

export default function StateNode({ id, label, status, x, y, role, roleInitial, roleColor }: StateNodeProps) {
  const { selectedEpicRef, setSelectedEpicRef, setIsContextPanelOpen } = usePlanContext();
  const isSelected = selectedEpicRef === id;
  const stateColor = stateColors[status] || stateColors.pending;
  const statusLabel = statusLabels[status] || status.replace(/-/g, ' ').toUpperCase();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEpicRef(id);
    setIsContextPanelOpen(true);
  };

  return (
    <foreignObject x={x} y={y} width="180" height="80" className="overflow-visible">
      <div
        onClick={handleClick}
        className={`flex flex-col p-2 rounded-lg border bg-surface transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md ${
          isSelected ? 'border-primary ring-2 ring-primary/20 scale-105' : 'border-border'
        }`}
        style={{ borderLeftWidth: '4px', borderLeftColor: stateColor, minHeight: '80px' }}
      >
        {/* Header: ID + Status */}
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] font-bold text-text-faint uppercase tracking-wider">
            {id}
          </span>
          <div 
            className="flex items-center gap-1 px-1 py-0.5 rounded-full text-[7px] font-bold uppercase"
            style={{ background: `${stateColor}15`, color: stateColor }}
          >
            <span 
              className={`w-1.5 h-1.5 rounded-full ${status !== 'passed' && status !== 'signoff' ? 'animate-pulse' : ''}`} 
              style={{ background: stateColor }} 
            />
            {statusLabel}
          </div>
        </div>
        
        {/* Label */}
        <h4 className="text-[11px] font-bold text-text-main line-clamp-1 leading-tight flex-1">
          {label}
        </h4>
        
        {/* Footer: Role Badge + Click hint */}
        <div className="flex items-center justify-between mt-1">
          {roleInitial ? (
            <div className="flex items-center gap-1.5">
              <div 
                className="w-4 h-4 rounded-full flex items-center justify-center text-[7px] font-extrabold text-white shadow-sm"
                style={{ background: roleColor || '#6366f1' }}
                title={role || 'Unknown Role'}
              >
                {roleInitial}
              </div>
              <span className="text-[8px] font-medium text-text-muted truncate max-w-[80px]">
                {role || 'unknown'}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[8px] font-medium text-text-muted">
              <span className="material-symbols-outlined text-[10px]">ads_click</span>
              Click to View
            </div>
          )}
          <span className="material-symbols-outlined text-[10px] text-text-faint opacity-0 group-hover:opacity-100 transition-opacity">
            open_in_new
          </span>
        </div>
      </div>
    </foreignObject>
  );
}
