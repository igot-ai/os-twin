'use client';

import React from 'react';
import { Epic, Lifecycle } from '@/types';
import StateNode from './StateNode';
import { mockLifecycle } from '@/lib/mock-data';

interface LifecycleVisualizerProps {
  epic: Epic;
}

export default function LifecycleVisualizer({ epic }: LifecycleVisualizerProps) {
  // Use epic.lifecycle if available (e.g. if we fetched with include_metadata=true)
  // Otherwise fallback to mockLifecycle
  const lifecycle = (epic as Epic & { lifecycle?: Lifecycle }).lifecycle || mockLifecycle;
  
  // Find current state index to determine completed vs future
  const stateKeys = Object.keys(lifecycle.states || {});
  const currentIndex = stateKeys.indexOf(epic.lifecycle_state ?? 'pending');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Visualizer Header */}
      <div className="p-4 border-b border-border bg-surface flex items-center justify-between shrink-0">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">account_tree</span> Lifecycle Visualizer
        </h2>
        <div className="flex items-center gap-4 text-[10px] text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-primary" aria-hidden="true"></span> Agent
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-text-faint" aria-hidden="true"></span> Built-in
          </span>
        </div>
      </div>

      {/* Visualizer Area */}
      <div className="flex-1 overflow-auto custom-scrollbar p-12 bg-[radial-gradient(var(--color-border)_1px,transparent_1px)] bg-[size:24px_24px]">
        <div className="flex items-center justify-center min-h-full">
          <div className="flex items-center gap-0">
            {stateKeys.map((stateKey, index) => {
              const stateData = lifecycle.states[stateKey];
              const isCurrent = stateKey === (epic.lifecycle_state || 'pending');
              const isCompleted = index < currentIndex;
              const hasNext = index < stateKeys.length - 1;

              return (
                <React.Fragment key={stateKey}>
                  <div className="relative">
                    <StateNode
                      state={stateKey.charAt(0).toUpperCase() + stateKey.slice(1)}
                      title={stateData.name}
                      type={stateData.type}
                      role={stateData.role}
                      isCurrent={isCurrent}
                      isCompleted={isCompleted}
                      timestamp={isCompleted ? "10:42:01" : undefined} // Mock timestamp
                    />
                    
                    {/* Arrow for completed states */}
                    {isCompleted && (
                      <div className="absolute -right-8 top-1/2 -translate-y-1/2 z-10">
                        <span className="material-symbols-outlined text-primary text-2xl font-bold bg-surface rounded-full shadow-sm" aria-hidden="true">
                          arrow_forward
                        </span>
                      </div>
                    )}
                    
                    {/* Done/Fail labels for current state */}
                    {isCurrent && hasNext && (
                      <div className="absolute left-full top-1/2 -translate-y-1/2 flex flex-col gap-1 px-4 z-10">
                        <div className="text-[9px] font-mono text-success bg-success-light px-1 border border-success/20 rounded">done</div>
                        <div className="text-[9px] font-mono text-danger bg-danger-light px-1 border border-danger/20 rounded">fail</div>
                      </div>
                    )}
                  </div>
                  
                  {hasNext && (
                    <div className={`h-0.5 shrink-0 ${
                      isCompleted 
                        ? 'bg-primary w-12' 
                        : 'w-24 border-t-2 border-dashed border-border'
                    }`}></div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
