'use client';

import React from 'react';
import { Epic, Lifecycle } from '@/types';
import StateNode from './StateNode';
import { useLifecycle, useAuditLog } from '@/hooks/use-war-room';
import { mockLifecycle } from '@/lib/mock-data';

interface LifecycleVisualizerProps {
  epic: Epic;
}

export default function LifecycleVisualizer({ epic }: LifecycleVisualizerProps) {
  // Fetch real lifecycle data from API
  const { lifecycle: fetchedLifecycle, isLoading: lcLoading } = useLifecycle(epic.plan_id, epic.epic_ref);
  const { auditLog } = useAuditLog(epic.plan_id, epic.epic_ref);
  
  // Use fetched lifecycle, then inline epic data, then mock as final fallback
  const lifecycle: Lifecycle = fetchedLifecycle 
    || (epic as Epic & { lifecycle?: Lifecycle }).lifecycle 
    || mockLifecycle;
  
  // Build timestamp map from audit log
  const stateTimestamps = new Map<string, string>();
  if (auditLog) {
    for (const entry of auditLog) {
      stateTimestamps.set(entry.to_state, entry.timestamp);
    }
  }

  // Find current state index to determine completed vs future
  const stateKeys = Object.keys(lifecycle.states || {});
  const currentIndex = stateKeys.indexOf(epic.lifecycle_state ?? 'pending');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Visualizer Header */}
      <div className="p-4 border-b border-border bg-surface flex items-center justify-between shrink-0">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">account_tree</span> Lifecycle Visualizer
          {lcLoading && (
            <span className="inline-block w-2 h-2 rounded-full bg-primary animate-pulse ml-1" title="Loading..." />
          )}
          {fetchedLifecycle && (
            <span className="text-[9px] font-mono text-success bg-success/10 px-1.5 py-0.5 rounded border border-success/20">LIVE</span>
          )}
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
              const timestamp = stateTimestamps.get(stateKey);

              // Show transition labels from the state machine
              const transitions = stateData.transitions || {};
              const transitionLabels = Object.keys(transitions);

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
                      timestamp={timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : undefined}
                    />
                    
                    {/* Arrow for completed states */}
                    {isCompleted && (
                      <div className="absolute -right-8 top-1/2 -translate-y-1/2 z-10">
                        <span className="material-symbols-outlined text-primary text-2xl font-bold bg-surface rounded-full shadow-sm" aria-hidden="true">
                          arrow_forward
                        </span>
                      </div>
                    )}
                    
                    {/* Transition labels for current state */}
                    {isCurrent && hasNext && transitionLabels.length > 0 && (
                      <div className="absolute left-full top-1/2 -translate-y-1/2 flex flex-col gap-1 px-4 z-10">
                        {transitionLabels.map(label => (
                          <div 
                            key={label}
                            className={`text-[9px] font-mono px-1 border rounded ${
                              label === 'pass' || label === 'done' 
                                ? 'text-success bg-success-light border-success/20'
                                : label === 'fail' || label === 'escalate'
                                  ? 'text-danger bg-danger-light border-danger/20'
                                  : 'text-text-muted bg-surface-hover border-border'
                            }`}
                          >
                            {label} → {transitions[label]}
                          </div>
                        ))}
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

      {/* Audit Log Summary */}
      {auditLog && auditLog.length > 0 && (
        <div className="px-4 py-2 border-t border-border bg-surface-hover/30 flex items-center gap-4 overflow-x-auto shrink-0">
          <span className="text-[9px] font-bold text-text-faint uppercase tracking-wider shrink-0">Audit:</span>
          {auditLog.map((entry, idx) => (
            <div key={idx} className="flex items-center gap-1 text-[9px] shrink-0">
              <span className="font-mono text-text-faint">{new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              <span className="text-text-muted">{entry.from_state}</span>
              <span className="material-symbols-outlined text-[10px] text-primary">arrow_forward</span>
              <span className="font-bold text-text-main">{entry.to_state}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
