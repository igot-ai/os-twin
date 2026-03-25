'use client';

import React from 'react';

interface StateNodeProps {
  state: string;
  title: string;
  type: 'agent' | 'builtin';
  role?: string;
  isCurrent: boolean;
  isCompleted: boolean;
  timestamp?: string;
}

export default function StateNode({
  state,
  title,
  type,
  role,
  isCurrent,
  isCompleted,
  timestamp
}: StateNodeProps) {
  const nodeStyles = isCurrent 
    ? 'w-56 p-5 bg-surface rounded-lg shadow-xl border-2 border-primary state-node-pulse relative z-10'
    : isCompleted
      ? 'w-48 p-4 bg-primary text-white rounded-lg shadow-lg border-2 border-primary'
      : 'w-48 p-4 bg-surface border-2 border-dashed border-border rounded-lg opacity-60 hover:opacity-100 transition-opacity';

  const badgeStyles = isCurrent
    ? 'bg-primary-muted text-primary border-primary-muted'
    : isCompleted
      ? 'bg-white/20 text-white border-transparent'
      : 'bg-background text-text-muted border-border';

  return (
    <div className={`relative group cursor-pointer ${nodeStyles}`}>
      {/* Current State Badge */}
      {isCurrent && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-primary text-white text-[9px] font-bold rounded-full uppercase">
          Current State
        </div>
      )}

      {/* State Label */}
      <div className={`text-[10px] font-bold uppercase mb-1 ${
        isCurrent ? 'text-primary' : isCompleted ? 'text-white/70' : 'text-text-muted'
      }`}>
        State: {state}
      </div>

      {/* Title */}
      <div className={`text-sm font-bold truncate ${
        isCurrent ? 'text-text-main' : isCompleted ? 'text-white' : 'text-text-muted'
      }`}>
        {title}
      </div>

      {/* Footer Info */}
      <div className={`mt-3 flex items-center justify-between`}>
        <div className="flex items-center gap-1.5">
          {role && (
             <div className="flex items-center gap-1.5">
               <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold ${
                 isCompleted ? 'bg-white text-primary' : 'bg-slate-800 text-white'
               }`}>
                 {role.substring(0, 2).toUpperCase()}
               </div>
               <span className={`text-[10px] font-medium ${
                 isCurrent ? 'text-text-muted' : isCompleted ? 'text-white/80' : 'text-text-faint'
               }`}>
                 {role}
               </span>
             </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${badgeStyles}`}>
            {type}
          </span>
          {timestamp && (
             <span className={`${isCompleted ? 'text-white/70' : 'text-text-faint'}`}>
               {timestamp}
             </span>
          )}
        </div>
      </div>
    </div>
  );
}
