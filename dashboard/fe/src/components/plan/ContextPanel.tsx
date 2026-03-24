'use client';

import React from 'react';
import { usePlanContext } from './PlanWorkspace';
import Link from 'next/link';
import { Epic, Plan } from '@/types';
import { stateColors } from './EpicCard';

export default function ContextPanel() {
  const { plan, epics, selectedEpicRef, setIsContextPanelOpen } = usePlanContext();
  
  const selectedEpic = epics?.find(e => e.epic_ref === selectedEpicRef);

  const handleClose = () => {
    setIsContextPanelOpen(false);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface relative">
      {/* Panel Header */}
      <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-alt/30">
        <h3 className="text-[10px] font-extrabold text-text-main uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px]">info</span>
          {selectedEpic ? 'EPIC Quick View' : 'Plan Summary'}
        </h3>
        <button 
          onClick={handleClose}
          className="p-1 hover:bg-surface-hover rounded-md text-text-faint hover:text-text-main transition-all"
        >
          <span className="material-symbols-outlined text-[18px]">close</span>
        </button>
      </div>

      {/* Panel Content */}
      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar bg-surface">
        {selectedEpic ? (
          <EpicQuickView epic={selectedEpic} />
        ) : (
          <PlanProgressSummary plan={plan} />
        )}
      </div>

      {/* Footer / Action Area */}
      {selectedEpic && (
        <div className="p-4 border-t border-border bg-surface-alt/30">
          <Link 
            href={`/plans/${plan?.plan_id}/epics/${selectedEpic.epic_ref}`}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-primary text-white text-xs font-bold hover:bg-primary-dark transition-all shadow-lg shadow-primary/20"
          >
            Open Full Detail
            <span className="material-symbols-outlined text-[16px]">open_in_new</span>
          </Link>
        </div>
      )}
    </div>
  );
}

function EpicQuickView({ epic }: { epic: Epic }) {
  const color = stateColors[epic.lifecycle_state ?? 'pending'] || stateColors.pending;
  const tasks = epic.tasks ?? [];
  
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-bold text-text-faint tracking-widest uppercase">
            {epic.epic_ref}
          </span>
          <div 
            className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase"
            style={{ background: `${color}15`, color: color }}
          >
            {(epic.lifecycle_state ?? 'pending').replace('-', ' ')}
          </div>
        </div>
        <h2 className="text-lg font-bold text-text-main leading-snug">
          {epic.title}
        </h2>
      </div>

      {/* Objective */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Objective</h4>
        <p className="text-sm text-text-muted leading-relaxed">
          {epic.objective || 'No objective specified.'}
        </p>
      </div>

      {/* Task Preview */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Tasks ({tasks.length})</h4>
          <span className="text-[10px] font-bold text-text-muted">
            {tasks.filter(t => t.completed).length} COMPLETED
          </span>
        </div>
        <div className="space-y-2">
          {tasks.slice(0, 5).map(task => (
            <div key={task.task_id} className="flex gap-2.5 items-start p-2.5 rounded-xl bg-surface-alt border border-border group transition-all hover:border-primary/20">
              <span className={`material-symbols-outlined text-[18px] transition-colors shrink-0 ${
                task.completed ? 'text-success' : 'text-text-faint group-hover:text-text-muted'
              }`}>
                {task.completed ? 'check_circle' : 'circle'}
              </span>
              <span className={`text-[12px] leading-tight font-medium ${task.completed ? 'text-text-faint line-through' : 'text-text-main'}`}>
                {task.description}
              </span>
            </div>
          ))}
          {tasks.length > 5 && (
            <div className="text-[10px] text-center font-bold text-text-faint uppercase py-2 border-t border-border mt-2">
              + {tasks.length - 5} more tasks
            </div>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-xl bg-surface-alt border border-border">
          <div className="text-[9px] font-bold text-text-faint uppercase mb-1">Assigned Role</div>
          <div className="text-xs font-bold text-text-main truncate">{epic.role}</div>
        </div>
        <div className="p-3 rounded-xl bg-surface-alt border border-border">
          <div className="text-[9px] font-bold text-text-faint uppercase mb-1">War Room</div>
          <div className="text-xs font-bold text-text-main truncate">#{epic.room_id || 'N/A'}</div>
        </div>
      </div>
    </div>
  );
}

function PlanProgressSummary({ plan }: { plan: Plan | undefined | null }) {
  if (!plan) return null;
  const pctComplete = plan.pct_complete ?? 0;
  const criticalPath = plan.critical_path ?? { completed: 0, total: 0 };
  const cpPct = criticalPath.total > 0 ? (criticalPath.completed / criticalPath.total) * 100 : 0;

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-right-2 duration-300">
      <div className="text-center bg-surface-alt/50 p-6 rounded-2xl border border-border shadow-inner">
        <div className="inline-flex items-center justify-center p-6 rounded-full bg-surface border-4 border-primary/5 mb-4 relative shadow-sm">
          <div className="text-2xl font-black text-primary">{pctComplete}%</div>
          <svg className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none">
            <circle
              cx="50%"
              cy="50%"
              r="44%"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
              className="text-primary"
              strokeDasharray={`${pctComplete * 2.76} 276`}
              strokeLinecap="round"
            />
          </svg>
        </div>
        <h3 className="text-sm font-bold text-text-main">Overall Completion</h3>
        <p className="text-[10px] text-text-faint uppercase mt-1 font-bold tracking-tight">
          Current Goal Progress
        </p>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-widest border-b border-border pb-1">
          Plan Health
        </h4>
        <div className="grid grid-cols-1 gap-2.5">
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-surface-alt border border-border group hover:border-primary/30 transition-all shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-lg">inventory_2</span>
              </div>
              <span className="text-xs font-bold text-text-muted uppercase tracking-tighter">Total EPICs</span>
            </div>
            <span className="text-lg font-black text-text-main">{plan.epic_count ?? 0}</span>
          </div>
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-surface-alt border border-border group hover:border-success/30 transition-all shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-success text-lg">check_circle</span>
              </div>
              <span className="text-xs font-bold text-text-muted uppercase tracking-tighter">Completed</span>
            </div>
            <span className="text-lg font-black text-text-main">{plan.completed_epics ?? 0}</span>
          </div>
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-surface-alt border border-border group hover:border-warning/30 transition-all shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center">
                <span className="material-symbols-outlined text-warning text-lg">bolt</span>
              </div>
              <span className="text-xs font-bold text-text-muted uppercase tracking-tighter">Active</span>
            </div>
            <span className="text-lg font-black text-text-main">{plan.active_epics ?? 0}</span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-widest border-b border-border pb-1">
          Critical Path
        </h4>
        <div className="p-4 rounded-xl bg-surface-alt border border-border space-y-3 shadow-sm">
          <div className="flex justify-between text-[11px] font-bold">
            <span className="text-text-muted">Milestone Progress</span>
            <span className="text-text-main font-black">
              {criticalPath.completed} / {criticalPath.total}
            </span>
          </div>
          <div className="h-1.5 w-full bg-border rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary"
              style={{ width: `${cpPct}%` }}
            />
          </div>
          <p className="text-[10px] text-text-faint leading-relaxed font-medium italic">
            Maintaining focus on critical path items ensures deadline compliance.
          </p>
        </div>
      </div>
    </div>
  );
}
