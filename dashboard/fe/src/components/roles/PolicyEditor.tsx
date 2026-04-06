'use client';

import { useState } from 'react';
import { Role, Policy, ConnectorInstance, PipelineAction, Trigger } from '@/types';
import { usePolicies } from '@/hooks/use-policies';
import { useConnectorInstances } from '@/hooks/use-connectors';
import { useSkills } from '@/hooks/use-skills';

interface PolicyEditorProps {
  role: Role;
  policy: Partial<Policy>;
  onClose: () => void;
}

export default function PolicyEditor({ role, policy, onClose }: PolicyEditorProps) {
  const { createPolicy, updatePolicy, refresh } = usePolicies(role.id);
  const { instances } = useConnectorInstances();
  const { skills } = useSkills();
  const [formData, setFormData] = useState<Partial<Policy>>({ ...policy });
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      if (formData.policy_id) {
        await updatePolicy(formData.policy_id, formData);
      } else {
        await createPolicy(formData);
      }
      refresh();
      onClose();
    } catch (error) {
      console.error('Failed to save policy:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const addStep = () => {
    const newStep: PipelineAction = { 
      action: 'fetch', 
      params: {} 
    };
    setFormData({
      ...formData,
      pipeline: [...(formData.pipeline || []), newStep]
    });
  };

  const updateStep = (index: number, updates: Partial<PipelineAction>) => {
    const newPipeline = [...(formData.pipeline || [])];
    newPipeline[index] = { ...newPipeline[index], ...updates };
    setFormData({ ...formData, pipeline: newPipeline });
  };

  const removeStep = (index: number) => {
    const newPipeline = (formData.pipeline || []).filter((_, i) => i !== index);
    setFormData({ ...formData, pipeline: newPipeline });
  };

  return (
    <div className="space-y-6 animate-in slide-in-from-right-4 duration-300">
      <div className="flex items-center gap-2 mb-2">
        <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg transition-colors">
          <span className="material-symbols-outlined text-base">arrow_back</span>
        </button>
        <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">
          {formData.policy_id ? 'Edit Policy' : 'Create New Policy'}
        </h3>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold text-text-muted px-1 uppercase tracking-wider">Policy Name</label>
          <input 
            type="text"
            className="w-full p-2.5 rounded-lg border text-sm font-semibold focus:ring-4 focus:ring-primary/10 transition-all"
            value={formData.name || ''}
            onChange={e => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g. Daily Gmail Digest"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-[10px] font-bold text-text-muted px-1 uppercase tracking-wider">Description</label>
          <textarea
            className="w-full p-2.5 rounded-lg border text-xs resize-none focus:ring-4 focus:ring-primary/10 transition-all"
            rows={2}
            value={formData.description || ''}
            onChange={e => setFormData({ ...formData, description: e.target.value })}
            placeholder="What does this policy do?"
          />
        </div>

        <div className="p-4 rounded-xl border bg-slate-50/50 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-text-faint">Trigger Configuration</h4>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[9px] font-bold text-text-faint px-1 uppercase tracking-wider">Type</label>
              <select 
                className="w-full p-2 rounded-lg border text-xs font-semibold bg-white"
                value={formData.trigger?.type}
                onChange={e => setFormData({ 
                  ...formData, 
                  trigger: { ...formData.trigger, type: e.target.value as any } as Trigger 
                })}
              >
                <option value="manual">Manual</option>
                <option value="schedule">Schedule (Cron)</option>
                <option value="role_activation">On Activation</option>
                <option value="webhook">Webhook</option>
              </select>
            </div>
            {formData.trigger?.type === 'schedule' && (
              <div className="space-y-1.5">
                <label className="text-[9px] font-bold text-text-faint px-1 uppercase tracking-wider">Cron Expr</label>
                <input 
                  type="text"
                  className="w-full p-2 rounded-lg border text-xs font-mono"
                  placeholder="0 0 * * *"
                  value={formData.trigger?.cron || ''}
                  onChange={e => setFormData({ 
                    ...formData, 
                    trigger: { ...formData.trigger, cron: e.target.value } as Trigger 
                  })}
                />
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-text-faint">Pipeline Steps</h4>
            <button 
              onClick={addStep}
              className="px-2 py-1 rounded bg-primary text-white text-[9px] font-bold uppercase hover:brightness-110 active:scale-95 transition-all"
            >
              Add Step
            </button>
          </div>

          <div className="space-y-3">
            {formData.pipeline?.map((step, index) => (
              <div key={index} className="relative p-4 rounded-xl border border-primary/20 bg-white shadow-sm animate-in zoom-in-95 duration-200">
                <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-primary text-white text-[9px] font-bold flex items-center justify-center">
                  {index + 1}
                </div>
                
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[9px] font-bold text-text-faint px-1 uppercase tracking-wider">Action</label>
                      <select 
                        className="w-full p-2 rounded-lg border text-xs font-semibold bg-white"
                        value={step.action}
                        onChange={e => updateStep(index, { action: e.target.value as any })}
                      >
                        <option value="fetch">Fetch Data</option>
                        <option value="filter">Filter Results</option>
                        <option value="transform">Transform Data</option>
                        <option value="store">Store to Memory</option>
                        <option value="notify">Notify (Slack/TG)</option>
                        <option value="forward">Forward to Role</option>
                        <option value="broadcast">Broadcast</option>
                      </select>
                    </div>

                    {step.action === 'fetch' && (
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-text-faint px-1 uppercase tracking-wider">Connector</label>
                        <select 
                          className="w-full p-2 rounded-lg border text-xs font-semibold bg-white"
                          value={step.connector_instance_id || ''}
                          onChange={e => updateStep(index, { connector_instance_id: e.target.value })}
                        >
                          <option value="">Select Connector...</option>
                          {instances?.map(inst => (
                            <option key={inst.id} value={inst.id}>{inst.name}</option>
                          ))}
                        </select>
                      </div>
                    )}

                    {step.action === 'transform' && (
                      <div className="space-y-1">
                        <label className="text-[9px] font-bold text-text-faint px-1 uppercase tracking-wider">Skill (Logic)</label>
                        <select 
                          className="w-full p-2 rounded-lg border text-xs font-semibold bg-white"
                          value={step.skill_ref || ''}
                          onChange={e => updateStep(index, { skill_ref: e.target.value })}
                        >
                          <option value="">Select Skill...</option>
                          {skills?.map(skill => (
                            <option key={skill.id} value={skill.name}>{skill.name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                  <button 
                    onClick={() => removeStep(index)}
                    className="p-1.5 hover:bg-rose-50 text-rose-600 rounded-lg transition-colors mt-4"
                  >
                    <span className="material-symbols-outlined text-base">close</span>
                  </button>
                </div>
              </div>
            ))}

            {(!formData.pipeline || formData.pipeline.length === 0) && (
              <div className="p-6 text-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50">
                <p className="text-[10px] text-text-faint italic">Add your first step to start building the pipeline.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="pt-4 flex gap-2">
        <button 
          onClick={handleSave}
          disabled={isSaving || !formData.name}
          className="flex-1 py-2.5 rounded-lg bg-primary text-white text-xs font-bold shadow-lg shadow-primary/20 hover:brightness-105 disabled:opacity-50 transition-all"
        >
          {isSaving ? 'Saving...' : 'Save Policy'}
        </button>
      </div>
    </div>
  );
}
