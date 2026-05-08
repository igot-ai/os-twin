'use client';

import { useState } from 'react';
import { usePlanContext } from './PlanWorkspace';
import Link from 'next/link';
import { Epic, Plan } from '@/types';
import { stateColors } from './EpicCard';
import { useWarRoomConfig, useAuditLog, useAgentInstances, useBrief } from '@/hooks/use-war-room';
import useSWR from 'swr';
import { EpicEditorPanel } from './EpicEditorPanel';

export default function ContextPanel() {
  const { plan, epics, selectedEpicRef, setIsContextPanelOpen, planId, parsedPlan, isEditingEpic, setIsEditingEpic } = usePlanContext();
  
  const selectedEpic = epics?.find(e => e.epic_ref === selectedEpicRef);

  // Bridge: look up the parsed EpicNode for the selected epic
  const editingEpicNode = selectedEpicRef && parsedPlan
    ? parsedPlan.epics.find(e => e.ref === selectedEpicRef) || null
    : null;

  const handleClose = () => {
    setIsContextPanelOpen(false);
    setIsEditingEpic(false);
  };

  const handleOpenEditor = () => {
    setIsEditingEpic(true);
  };

  const handleCloseEditor = () => {
    setIsEditingEpic(false);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface relative">
      {/* Panel Header */}
      <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-alt/30">
        <h3 className="text-[10px] font-extrabold text-text-main uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-[16px]">{isEditingEpic ? 'edit' : 'info'}</span>
          {selectedEpic ? (isEditingEpic ? 'Edit EPIC' : 'EPIC Quick View') : 'Plan Summary'}
        </h3>
        <div className="flex items-center gap-1">
          {selectedEpic && editingEpicNode && !isEditingEpic && (
            <button
              onClick={handleOpenEditor}
              className="p-1 hover:bg-primary/10 rounded-md text-text-faint hover:text-primary transition-all"
              title="Edit this EPIC"
            >
              <span className="material-symbols-outlined text-[18px]">edit</span>
            </button>
          )}
          <button 
            onClick={handleClose}
            className="p-1 hover:bg-surface-hover rounded-md text-text-faint hover:text-text-main transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>
      </div>

      {/* Panel Content */}
      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar bg-surface">
        {selectedEpic ? (
          <EpicQuickView epic={selectedEpic} planId={planId} />
        ) : (
          <PlanProgressSummary plan={plan} />
        )}
      </div>

      {/* Edit Epic Drawer (overlay) */}
      <EpicEditorPanel
        epic={editingEpicNode}
        isOpen={isEditingEpic && !!editingEpicNode}
        onClose={handleCloseEditor}
      />
    </div>
  );
}

// ─── Epic Quick View Tab System ──────────────────────────────────────────────

type EpicTab = 'overview' | 'channel' | 'transitions';

function EpicQuickView({ epic, planId }: { epic: Epic; planId: string }) {
  const [activeTab, setActiveTab] = useState<EpicTab>('overview');
  
  const tabs: { id: EpicTab; label: string; icon: string }[] = [
    { id: 'overview', label: 'Overview', icon: 'dashboard' },
    { id: 'channel', label: 'Channel', icon: 'forum' },
    { id: 'transitions', label: 'Transitions', icon: 'sync_alt' },
  ];

  return (
    <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
      {/* Epic Header */}
      <EpicHeader epic={epic} />

      {/* Tab Bar */}
      <div className="flex border-b border-border">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-[10px] font-bold uppercase tracking-wider border-b-2 transition-all ${
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-text-faint hover:text-text-muted'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && <OverviewTab epic={epic} planId={planId} />}
      {activeTab === 'channel' && <ChannelTab roomId={epic.room_id} planId={planId} />}
      {activeTab === 'transitions' && <TransitionsTab epicRef={epic.epic_ref} planId={planId} />}
    </div>
  );
}

// ─── Epic Header ─────────────────────────────────────────────────────────────

function EpicHeader({ epic }: { epic: Epic }) {
  const color = stateColors[epic.lifecycle_state ?? 'pending'] || stateColors.pending;

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-bold text-text-faint tracking-widest uppercase">
          {epic.epic_ref}
        </span>
        <div 
          className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase flex items-center gap-1"
          style={{ background: `${color}15`, color: color }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
          {(epic.lifecycle_state ?? 'pending').replace(/-/g, ' ')}
        </div>
      </div>
      <h2 className="text-lg font-bold text-text-main leading-snug">
        {epic.title}
      </h2>
    </div>
  );
}

// ─── Overview Tab ────────────────────────────────────────────────────────────

function OverviewTab({ epic, planId }: { epic: Epic; planId: string }) {
  const { config } = useWarRoomConfig(planId, epic.epic_ref);
  const { agents } = useAgentInstances(planId, epic.epic_ref);
  useBrief(planId, epic.epic_ref);

  return (
    <div className="space-y-5">
      {/* Assignment Info */}
      {config?.assignment && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Assignment</h4>
          <div className="p-3 rounded-xl bg-surface-alt border border-border">
            <div className="text-xs font-bold text-text-main mb-1">{config.assignment.title}</div>
            <p className="text-[11px] text-text-muted leading-relaxed line-clamp-3">
              {config.assignment.description?.split('\n')[0] || 'No description'}
            </p>
          </div>
        </div>
      )}

      {/* Role & Room Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 rounded-xl bg-surface-alt border border-border">
          <div className="text-[9px] font-bold text-text-faint uppercase mb-1">Assigned Role</div>
          <div className="text-xs font-bold text-text-main truncate">{epic.role || config?.assignment?.assigned_role || 'N/A'}</div>
        </div>
        <div className="p-3 rounded-xl bg-surface-alt border border-border">
          <div className="text-[9px] font-bold text-text-faint uppercase mb-1">War Room</div>
          <div className="text-xs font-bold text-text-main truncate">#{epic.room_id || 'N/A'}</div>
        </div>
      </div>

      {/* Agent Instances */}
      {agents && agents.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">
            Agent Instances ({agents.length})
          </h4>
          <div className="space-y-2">
            {agents.map((agent: any, idx: number) => {
              const statusColor = agent.status === 'completed' ? '#10b981' : agent.status === 'running' ? '#3b82f6' : '#f59e0b';
              return (
                <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-alt border border-border">
                  <div className="flex items-center gap-2">
                    <div 
                      className="w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-extrabold text-white"
                      style={{ background: statusColor }}
                    >
                      {(agent.role || '??').charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-[11px] font-bold text-text-main">{agent.display_name || agent.role}</div>
                      <div className="text-[9px] text-text-faint font-mono">{agent.model}</div>
                    </div>
                  </div>
                  <span 
                    className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full"
                    style={{ background: `${statusColor}15`, color: statusColor }}
                  >
                    {agent.status}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Constraints */}
      {config?.constraints && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Constraints</h4>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2 rounded-lg bg-surface-alt border border-border text-center">
              <div className="text-[8px] font-bold text-text-faint uppercase">Retries</div>
              <div className="text-sm font-black text-text-main">{config.status?.retries ?? 0}/{config.constraints.max_retries}</div>
            </div>
            <div className="p-2 rounded-lg bg-surface-alt border border-border text-center">
              <div className="text-[8px] font-bold text-text-faint uppercase">Timeout</div>
              <div className="text-sm font-black text-text-main">{Math.round(config.constraints.timeout_seconds / 60)}m</div>
            </div>
            <div className="p-2 rounded-lg bg-surface-alt border border-border text-center">
              <div className="text-[8px] font-bold text-text-faint uppercase">Budget</div>
              <div className="text-sm font-black text-text-main">{Math.round(config.constraints.budget_tokens_max / 1000)}k</div>
            </div>
          </div>
        </div>
      )}

      {/* Quality Requirements */}
      {config?.goals?.quality_requirements && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Quality Gates</h4>
          <div className="flex flex-wrap gap-2">
            {config.goals.quality_requirements.lint_clean && (
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                ✓ Lint Clean
              </span>
            )}
            {config.goals.quality_requirements.security_scan_pass && (
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 border border-blue-500/20">
                ✓ Security Scan
              </span>
            )}
            {config.goals.quality_requirements.test_coverage_min > 0 && (
              <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 border border-purple-500/20">
                ≥{config.goals.quality_requirements.test_coverage_min}% Coverage
              </span>
            )}
          </div>
        </div>
      )}

      {/* Skill Refs */}
      {config?.skill_refs && config.skill_refs.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">
            Skill Pack ({config.skill_refs.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {config.skill_refs.map((skill: string) => (
              <span key={skill} className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 border border-amber-500/20">
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tasks from TASKS.md */}
      <TasksSection epicRef={epic.epic_ref} planId={planId} />

      {/* Dependencies */}
      {epic.depends_on && epic.depends_on.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">Dependencies</h4>
          <div className="flex flex-wrap gap-1.5">
            {epic.depends_on.map(dep => (
              <span key={dep} className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 border border-blue-500/20">
                {dep}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Tasks Section (TASKS.md) ───────────────────────────────────────────────

function TasksSection({ epicRef, planId }: { epicRef: string; planId: string }) {
  const { data, isLoading } = useSWR<{ tasks: any[]; count: number; raw: string }>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/tasks` : null
  );

  if (isLoading) return null;
  const tasks = data?.tasks || [];
  if (tasks.length === 0) return null;

  const completedCount = tasks.filter((t: any) => t.completed).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-[10px] font-extrabold text-text-faint uppercase tracking-wider">
          Tasks ({tasks.length})
        </h4>
        <span className="text-[10px] font-bold text-text-muted">
          {completedCount}/{tasks.length} done
        </span>
      </div>
      
      {/* Progress bar */}
      <div className="h-1 w-full bg-border/50 rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all duration-500 ${completedCount === tasks.length ? 'bg-success' : 'bg-primary'}`}
          style={{ width: `${tasks.length > 0 ? (completedCount / tasks.length) * 100 : 0}%` }}
        />
      </div>

      <div className="space-y-2">
        {tasks.map((task: any, idx: number) => (
          <div key={task.task_id || idx} className="p-2.5 rounded-xl bg-surface-alt border border-border group transition-all hover:border-primary/20">
            <div className="flex gap-2.5 items-start">
              <span className={`material-symbols-outlined text-[18px] shrink-0 mt-0.5 ${
                task.completed ? 'text-success' : 'text-text-faint'
              }`}>
                {task.completed ? 'check_circle' : 'circle'}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] font-bold text-text-faint tracking-wider uppercase">{task.task_id}</span>
                </div>
                <span className={`text-[11px] leading-tight font-medium block ${task.completed ? 'text-text-faint line-through' : 'text-text-main'}`}>
                  {task.description}
                </span>
                {/* Acceptance Criteria */}
                {task.acceptance_criteria && task.acceptance_criteria.length > 0 && (
                  <div className="mt-1.5 space-y-1">
                    {task.acceptance_criteria.map((ac: string, acIdx: number) => (
                      <div key={acIdx} className="flex items-start gap-1.5 text-[10px] text-text-muted">
                        <span className="material-symbols-outlined text-[10px] text-purple-500 shrink-0 mt-0.5">verified</span>
                        <span>{ac}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Channel Tab ─────────────────────────────────────────────────────────────

const messageTypeStyles: Record<string, { icon: string; color: string }> = {
  task: { icon: 'assignment', color: '#3b82f6' },
  'design-guidance': { icon: 'architecture', color: '#8b5cf6' },
  'plan-approve': { icon: 'check_circle', color: '#10b981' },
  'plan-reject': { icon: 'cancel', color: '#ef4444' },
  'qa-result': { icon: 'verified', color: '#06b6d4' },
  done: { icon: 'task_alt', color: '#10b981' },
  fix: { icon: 'build', color: '#f59e0b' },
  error: { icon: 'error', color: '#ef4444' },
  escalate: { icon: 'priority_high', color: '#ef4444' },
};

function ChannelTab({ roomId, planId }: { roomId?: string; planId: string }) {
  // Fetch channel messages via the rooms endpoint
  const { data, isLoading } = useSWR<{ messages: any[] }>(
    planId && roomId ? `/plans/${planId}/rooms/${roomId}/channel` : null
  );
  const messages = data?.messages;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="animate-spin material-symbols-outlined text-primary">progress_activity</span>
      </div>
    );
  }

  const msgs = messages || [];

  if (msgs.length === 0) {
    return (
      <div className="text-center py-12">
        <span className="material-symbols-outlined text-3xl text-text-faint mb-2 block">forum</span>
        <p className="text-xs text-text-faint font-medium">No channel messages yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-[10px] font-bold text-text-faint uppercase tracking-wider">
        {msgs.length} Messages
      </div>
      {msgs.map((msg: any, idx: number) => {
        const style = messageTypeStyles[msg.type] || { icon: 'chat', color: '#94a3b8' };
        const time = msg.ts ? new Date(msg.ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';
        const date = msg.ts ? new Date(msg.ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
        
        return (
          <div key={msg.id || idx} className="p-3 rounded-xl bg-surface-alt border border-border space-y-2 hover:border-primary/20 transition-colors">
            {/* Message Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div 
                  className="w-5 h-5 rounded-full flex items-center justify-center"
                  style={{ background: `${style.color}15` }}
                >
                  <span className="material-symbols-outlined text-[12px]" style={{ color: style.color }}>{style.icon}</span>
                </div>
                <span className="text-[10px] font-bold text-text-main capitalize">{msg.from}</span>
                <span className="text-[9px] text-text-faint">→</span>
                <span className="text-[10px] font-bold text-text-muted capitalize">{msg.to}</span>
              </div>
              <div className="text-right">
                <div className="text-[9px] font-mono text-text-faint">{time}</div>
                <div className="text-[8px] text-text-faint">{date}</div>
              </div>
            </div>
            
            {/* Message Type Badge */}
            <span 
              className="inline-flex items-center gap-1 text-[8px] font-bold uppercase px-1.5 py-0.5 rounded-full"
              style={{ background: `${style.color}10`, color: style.color }}
            >
              {msg.type?.replace(/-/g, ' ')}
            </span>

            {/* Message Body */}
            <p className="text-[11px] text-text-muted leading-relaxed line-clamp-4 whitespace-pre-wrap">
              {msg.body}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ─── Transitions Tab ─────────────────────────────────────────────────────────

function TransitionsTab({ epicRef, planId }: { epicRef: string; planId: string }) {
  const { auditLog, isLoading } = useAuditLog(planId, epicRef);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="animate-spin material-symbols-outlined text-primary">progress_activity</span>
      </div>
    );
  }

  const transitions = auditLog || [];

  if (transitions.length === 0) {
    return (
      <div className="text-center py-12">
        <span className="material-symbols-outlined text-3xl text-text-faint mb-2 block">sync_alt</span>
        <p className="text-xs text-text-faint font-medium">No state transitions recorded</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="text-[10px] font-bold text-text-faint uppercase tracking-wider mb-3">
        {transitions.length} State Transitions
      </div>
      
      {/* Timeline */}
      <div className="relative pl-6">
        {/* Vertical line */}
        <div className="absolute left-[9px] top-0 bottom-0 w-[2px] bg-border" />
        
        {transitions.map((tr: any, idx: number) => {
          const fromColor = stateColors[tr.from_state] || '#94a3b8';
          const toColor = stateColors[tr.to_state] || '#94a3b8';
          const time = tr.timestamp ? new Date(tr.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
          const date = tr.timestamp ? new Date(tr.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
          
          return (
            <div key={idx} className="relative pb-4 last:pb-0">
              {/* Dot on timeline */}
              <div 
                className="absolute left-[-15px] top-1 w-3 h-3 rounded-full border-2 border-surface z-10"
                style={{ background: toColor }}
              />
              
              {/* Content */}
              <div className="p-2.5 rounded-lg bg-surface-alt border border-border hover:border-primary/20 transition-colors">
                <div className="flex items-center gap-2 mb-1">
                  <span 
                    className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full"
                    style={{ background: `${fromColor}15`, color: fromColor }}
                  >
                    {tr.from_state?.replace(/-/g, ' ')}
                  </span>
                  <span className="material-symbols-outlined text-[12px] text-text-faint">arrow_forward</span>
                  <span 
                    className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full"
                    style={{ background: `${toColor}15`, color: toColor }}
                  >
                    {tr.to_state?.replace(/-/g, ' ')}
                  </span>
                </div>
                <div className="text-[9px] font-mono text-text-faint">
                  {date} {time}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Plan Progress Summary (when no epic selected) ──────────────────────────

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
