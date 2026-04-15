'use client';


import { usePlanContext } from '../PlanWorkspace';
import DAGViewer from '../DAGViewer';

export default function DAGTab() {
  const { progress } = usePlanContext();
  const isLive = !!(progress?.rooms && progress.rooms.length > 0);

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
              {isLive ? 'Visualizing the execution path and dependency graph' : 'Authoring dependency graph and execution path'}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded-md border ${
            isLive ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-amber-50 text-amber-600 border-amber-100'
          }`}>
            Status: {isLive ? 'Live' : 'Authoring'}
          </span>
        </div>
      </div>
      
      {/* Content Area */}
      <div className="flex-1 min-h-0">
        <DAGViewer mode={isLive ? 'live' : 'authoring'} />
      </div>
    </div>
  );
}

