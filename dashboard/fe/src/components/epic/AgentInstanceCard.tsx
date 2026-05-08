'use client';


import { AgentInstance } from '@/types';

interface AgentInstanceCardProps {
  agent: AgentInstance;
}

const modelColors: Record<string, string> = {
  'gemini': '#4285f4',
  'claude': '#d97706',
  'gpt': '#10b981',
};

const statusIcons: Record<string, { icon: string; color: string; bg: string }> = {
  completed: { icon: 'check_circle', color: '#10b981', bg: 'bg-emerald-500/10' },
  running: { icon: 'play_circle', color: '#3b82f6', bg: 'bg-blue-500/10' },
  failed: { icon: 'error', color: '#ef4444', bg: 'bg-red-500/10' },
  pending: { icon: 'schedule', color: '#94a3b8', bg: 'bg-slate-500/10' },
};

export default function AgentInstanceCard({ agent }: AgentInstanceCardProps) {
  const status = statusIcons[agent.status] || statusIcons.pending;
  const modelProvider = Object.keys(modelColors).find(k => agent.model.toLowerCase().includes(k));
  const modelColor = modelProvider ? modelColors[modelProvider] : '#6366f1';

  return (
    <div className="p-3 rounded-xl border border-border bg-surface hover:border-primary/30 transition-all group shadow-sm">
      {/* Header: Role + Status */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div 
            className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[10px] font-bold shadow-inner"
            style={{ background: modelColor }}
          >
            {agent.role.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="text-xs font-bold text-text-main">{agent.display_name}</div>
            <div className="text-[9px] text-text-faint font-mono">#{agent.instance_id}</div>
          </div>
        </div>
        <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold ${status.bg}`}>
          <span className="material-symbols-outlined text-[12px]" style={{ color: status.color }}>{status.icon}</span>
          <span style={{ color: status.color }}>{agent.status}</span>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        <div className="p-2 rounded-lg bg-surface-alt border border-border/50">
          <div className="text-[8px] font-bold text-text-faint uppercase tracking-wider">Model</div>
          <div className="text-[10px] font-bold text-text-main truncate" title={agent.model}>
            {agent.model}
          </div>
        </div>
        <div className="p-2 rounded-lg bg-surface-alt border border-border/50">
          <div className="text-[8px] font-bold text-text-faint uppercase tracking-wider">Role</div>
          <div className="text-[10px] font-bold text-text-main capitalize">{agent.role}</div>
        </div>
        <div className="p-2 rounded-lg bg-surface-alt border border-border/50 col-span-2">
          <div className="text-[8px] font-bold text-text-faint uppercase tracking-wider">Assigned At</div>
          <div className="text-[10px] font-mono text-text-main">
            {new Date(agent.assigned_at).toLocaleString([], {
              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            })}
          </div>
        </div>
      </div>

      {/* Config Override indicator */}
      {agent.config_override && Object.keys(agent.config_override).length > 0 && (
        <div className="mt-2 px-2 py-1.5 rounded-md bg-amber-500/5 border border-amber-500/15 text-[9px] text-amber-600 font-medium flex items-center gap-1">
          <span className="material-symbols-outlined text-[11px]">tune</span>
          {Object.keys(agent.config_override).length} config override{Object.keys(agent.config_override).length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
