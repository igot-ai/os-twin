'use client';

import { useState } from 'react';
import { Role, Policy, ConnectorInstance } from '@/types';
import { usePolicies, usePolicyHistory } from '@/hooks/use-policies';
import { useConnectorInstances } from '@/hooks/use-connectors';
import PolicyEditor from './PolicyEditor';

interface PolicyTabProps {
  role: Role;
}

function PolicyHistory({ policyId }: { policyId: string }) {
  const { history, isLoading } = usePolicyHistory(policyId);

  if (isLoading) return <div className="p-4 text-[10px] text-text-faint animate-pulse">Loading history...</div>;
  if (!history || history.length === 0) return <div className="p-4 text-[10px] text-text-faint italic">No execution history found.</div>;

  return (
    <div className="mt-2 space-y-2 border-t pt-2 max-h-40 overflow-y-auto custom-scrollbar">
      {history.map((run, i) => (
        <div key={i} className="flex items-center justify-between text-[10px]">
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${run.status === 'success' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-text-muted font-mono">{new Date(run.finished_at).toLocaleString()}</span>
          </div>
          {run.error && <span className="text-rose-500 truncate max-w-[150px]">{run.error}</span>}
          {run.status === 'success' && <span className="text-emerald-600 font-bold uppercase tracking-wider">Success</span>}
        </div>
      ))}
    </div>
  );
}

export default function PolicyTab({ role }: PolicyTabProps) {
  const { policies, isLoading, deletePolicy, executePolicy } = usePolicies(role.id);
  const { instances } = useConnectorInstances();
  const [isEditing, setIsEditing] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Partial<Policy> | null>(null);
  const [expandedPolicyId, setExpandedPolicyId] = useState<string | null>(null);

  const handleCreate = () => {
    setEditingPolicy({
      name: '',
      description: '',
      trigger: { type: 'manual', role_id: role.id },
      pipeline: [],
      enabled: true,
    });
    setIsEditing(true);
  };

  const handleEdit = (policy: Policy) => {
    setEditingPolicy(policy);
    setIsEditing(true);
  };

  if (isEditing && editingPolicy) {
    return (
      <PolicyEditor 
        role={role} 
        policy={editingPolicy} 
        onClose={() => setIsEditing(false)} 
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Data Policies</h3>
        <button 
          onClick={handleCreate}
          className="flex items-center gap-1 px-2 py-1 rounded bg-primary/10 text-primary text-[10px] font-bold hover:bg-primary/20 transition-all"
        >
          <span className="material-symbols-outlined text-[14px]">add</span>
          New Policy
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-24 rounded-xl border border-slate-100 bg-slate-50/50 animate-pulse" />
          ))}
        </div>
      ) : policies?.length === 0 ? (
        <div className="p-8 text-center rounded-2xl border-2 border-dashed border-slate-100 bg-slate-50/30">
          <span className="material-symbols-outlined text-3xl text-slate-200 mb-2">policy</span>
          <p className="text-xs text-text-faint italic font-medium">No policies defined for this role.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {policies?.map(policy => (
            <div 
              key={policy.policy_id}
              className="p-4 rounded-xl border bg-white shadow-sm hover:shadow-md transition-all group"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h4 className="text-sm font-bold text-text-main group-hover:text-primary transition-colors">{policy.name}</h4>
                  <p className="text-[10px] text-text-faint mt-0.5 line-clamp-1">{policy.description || 'No description'}</p>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => setExpandedPolicyId(expandedPolicyId === policy.policy_id ? null : policy.policy_id)}
                    className={`p-1.5 rounded-lg transition-colors ${expandedPolicyId === policy.policy_id ? 'bg-primary/10 text-primary' : 'hover:bg-slate-100 text-text-muted'}`}
                    title="View History"
                  >
                    <span className="material-symbols-outlined text-base">history</span>
                  </button>
                  <button 
                    onClick={() => executePolicy(policy.policy_id)}
                    className="p-1.5 hover:bg-emerald-50 text-emerald-600 rounded-lg transition-colors"
                    title="Run Now"
                  >
                    <span className="material-symbols-outlined text-base">play_arrow</span>
                  </button>
                  <button 
                    onClick={() => handleEdit(policy)}
                    className="p-1.5 hover:bg-slate-100 text-text-muted rounded-lg transition-colors"
                    title="Edit"
                  >
                    <span className="material-symbols-outlined text-base">edit</span>
                  </button>
                  <button 
                    onClick={() => deletePolicy(policy.policy_id)}
                    className="p-1.5 hover:bg-rose-50 text-rose-600 rounded-lg transition-colors"
                    title="Delete"
                  >
                    <span className="material-symbols-outlined text-base">delete</span>
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-wider text-text-faint">
                <div className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-[12px]">schedule</span>
                  {policy.trigger.type}
                </div>
                <div className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-[12px]">reorder</span>
                  {policy.pipeline.length} steps
                </div>
                {policy.last_run_at && (
                  <div className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px]">history</span>
                    Last run {new Date(policy.last_run_at).toLocaleDateString()}
                  </div>
                )}
              </div>
              
              {expandedPolicyId === policy.policy_id && (
                <div className="mt-4 pt-4 border-t animate-in slide-in-from-top-2 duration-300">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-xs text-text-faint">history</span>
                    <h5 className="text-[10px] font-bold uppercase tracking-widest text-text-faint">Execution History</h5>
                  </div>
                  <PolicyHistory policyId={policy.policy_id} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
