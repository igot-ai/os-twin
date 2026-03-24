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
}

export default function StateNode({ id, label, status, x, y }: StateNodeProps) {
  const { selectedEpicRef, setSelectedEpicRef, setIsContextPanelOpen } = usePlanContext();
  const isSelected = selectedEpicRef === id;
  const stateColor = stateColors[status] || stateColors.pending;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // prevent pan if implemented
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
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] font-bold text-text-faint uppercase tracking-wider">
            {id}
          </span>
          <div 
            className="flex items-center gap-1 px-1 py-0.5 rounded-full text-[7px] font-bold uppercase"
            style={{ background: `${stateColor}15`, color: stateColor }}
          >
            <span className="w-1 h-1 rounded-full" style={{ background: stateColor }} />
            {status.replace('-', ' ')}
          </div>
        </div>
        
        <h4 className="text-[11px] font-bold text-text-main line-clamp-2 leading-tight flex-1">
          {label}
        </h4>
        
        <div className="flex items-center gap-1 mt-1 text-[8px] font-medium text-text-muted">
          <span className="material-symbols-outlined text-[10px]">ads_click</span>
          Click to View
        </div>
      </div>
    </foreignObject>
  );
}
