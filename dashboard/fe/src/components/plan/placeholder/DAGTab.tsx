'use client';

import React from 'react';
import DAGViewer from '../DAGViewer';

export default function DAGTab() {
  return (
    <div className="w-full h-full flex flex-col bg-surface border-l border-border animate-in fade-in duration-500">
      {/* Tab Header Area */}
      <div className="px-5 py-4 border-b border-border bg-surface-alt/20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shadow-sm border border-primary/20">
            <span className="material-symbols-outlined text-[20px]">account_tree</span>
          </div>
          <div>
            <h2 className="text-xs font-bold text-text-main uppercase tracking-widest">
              Plan Dependency DAG
            </h2>
            <p className="text-[10px] font-medium text-text-faint uppercase">
              Visualizing the execution path and dependency graph
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-text-faint uppercase bg-surface-alt px-2 py-1 rounded-md border border-border">
            Status: Active
          </span>
        </div>
      </div>
      
      {/* Content Area */}
      <div className="flex-1 min-h-0">
        <DAGViewer />
      </div>
    </div>
  );
}

