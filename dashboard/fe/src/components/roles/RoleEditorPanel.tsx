'use client';

import { useState, useEffect } from 'react';
import { mutate } from 'swr';
import { Role } from '@/types';
import ProviderSelector from './ProviderSelector';
import SkillChipInput from './SkillChipInput';
import TestConnectionButton from './TestConnectionButton';

interface RoleEditorPanelProps {
  role?: Role;
  isOpen: boolean;
  onClose: () => void;
  existingRoles: Role[];
}

const modelVersions: Record<string, string[]> = {
  claude: ['claude-3-5-sonnet-20240620', 'claude-3-opus-20240229', 'claude-3-haiku-20240307', 'claude-sonnet-4-6'],
  gpt: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'gpt-4o-mini'],
  gemini: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.5-pro'],
  custom: ['v1-alpha', 'v1-beta', 'v2-stable'],
};

export default function RoleEditorPanel({ role, isOpen, onClose, existingRoles }: RoleEditorPanelProps) {
  const [formData, setFormData] = useState<Partial<Role>>({
    name: '',
    provider: 'claude',
    version: 'claude-sonnet-4-6',
    temperature: 0.3,
    budget_tokens_max: 500000,
    max_retries: 3,
    timeout_seconds: 900,
    skill_refs: [],
    system_prompt_override: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (role) {
      setFormData(role);
    } else {
      setFormData({
        name: '',
        provider: 'claude',
        version: 'claude-sonnet-4-6',
        temperature: 0.3,
        budget_tokens_max: 500000,
        max_retries: 3,
        timeout_seconds: 900,
        skill_refs: [],
        system_prompt_override: '',
      });
    }
    setErrors({});
  }, [role, isOpen]);

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.name) newErrors.name = 'Name is required';
    if (existingRoles.some(r => r.name.toLowerCase() === formData.name?.toLowerCase() && r.id !== role?.id)) {
      newErrors.name = 'Role name already exists';
    }
    if (formData.temperature === undefined || formData.temperature < 0 || formData.temperature > 2) {
      newErrors.temperature = 'Temperature must be between 0 and 2';
    }
    if (!formData.version) newErrors.version = 'Model version is required';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;

    setIsSaving(true);
    try {
      const url = role ? `/api/roles/${role.id}` : '/api/roles';
      const method = role ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        mutate('/api/roles');
        onClose();
      }
    } catch (error) {
      console.error('Failed to save role:', error);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end animate-in fade-in duration-300">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Panel */}
      <div 
        className="relative w-full max-w-[420px] h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-500 overflow-hidden"
        style={{ background: 'var(--color-surface)' }}
      >
        {/* Header */}
        <div className="p-6 border-b flex items-center justify-between sticky top-0 z-10" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
          <div>
            <h2 className="text-xl font-extrabold" style={{ color: 'var(--color-text-main)' }}>{role ? 'Edit Role' : 'New Role'}</h2>
            <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>Configure agent identity and model binding</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Form Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar pb-24">
          
          {/* Section: Identity */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">01</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Identity & Context</h3>
            </div>
            
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-text-muted px-1 uppercase tracking-wider">Role Name</label>
              <input 
                type="text"
                placeholder="e.g. Frontend Engineer"
                className={`w-full p-3 rounded-xl border text-sm font-semibold transition-all focus:ring-4 focus:ring-primary/10 ${errors.name ? 'border-red-500 bg-red-50' : 'bg-white'}`}
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
              />
              {errors.name && <p className="text-[10px] font-bold text-red-500 px-1">{errors.name}</p>}
            </div>
          </div>

          {/* Section: Model Binding */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">02</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Model Binding</h3>
            </div>
            
            <ProviderSelector 
              value={formData.provider || 'claude'}
              onChange={p => setFormData({ ...formData, provider: p, version: modelVersions[p][0] })}
            />

            <div className="space-y-1.5 mt-4">
              <label className="text-[11px] font-bold text-text-muted px-1 uppercase tracking-wider">Model Version</label>
              <select 
                className="w-full p-3 rounded-xl border bg-white text-sm font-semibold shadow-sm focus:ring-4 focus:ring-primary/10"
                value={formData.version}
                onChange={e => setFormData({ ...formData, version: e.target.value })}
              >
                {modelVersions[formData.provider || 'claude'].map(v => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
            
            {role && <TestConnectionButton roleId={role.id} />}
          </div>

          {/* Section: Parameters */}
          <div className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">03</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Sampling Parameters</h3>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between px-1">
                <label className="text-[11px] font-bold text-text-muted uppercase tracking-wider">Temperature</label>
                <span className="text-xs font-mono font-bold text-primary">{formData.temperature}</span>
              </div>
              <input 
                type="range"
                min="0"
                max="2"
                step="0.1"
                className="w-full h-1.5 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary"
                value={formData.temperature}
                onChange={e => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
              />
              <div className="flex justify-between text-[10px] font-bold text-text-faint px-1">
                <span>Deterministic</span>
                <span>Balanced</span>
                <span>Creative</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-text-muted px-1 uppercase tracking-wider">Budget Tokens</label>
                <input 
                  type="number"
                  className="w-full p-3 rounded-xl border bg-white text-sm font-mono font-semibold"
                  value={formData.budget_tokens_max}
                  onChange={e => setFormData({ ...formData, budget_tokens_max: parseInt(e.target.value) })}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-text-muted px-1 uppercase tracking-wider">Timeout (s)</label>
                <input 
                  type="number"
                  className="w-full p-3 rounded-xl border bg-white text-sm font-mono font-semibold"
                  value={formData.timeout_seconds}
                  onChange={e => setFormData({ ...formData, timeout_seconds: parseInt(e.target.value) })}
                />
              </div>
            </div>
          </div>

          {/* Section: Skills */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">04</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Skill Matrix</h3>
            </div>
            
            <SkillChipInput 
              selectedSkillRefs={formData.skill_refs || []}
              onChange={refs => setFormData({ ...formData, skill_refs: refs })}
            />
          </div>

          {/* Section: Advanced */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">05</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-text-faint">Advanced Configuration</h3>
            </div>
            
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-text-muted px-1 uppercase tracking-wider">System Prompt Override</label>
              <textarea 
                rows={6}
                placeholder="Optional: Custom system instructions for this role..."
                className="w-full p-3 rounded-xl border bg-white text-xs font-mono resize-none focus:ring-4 focus:ring-primary/10 transition-all"
                value={formData.system_prompt_override || ''}
                onChange={e => setFormData({ ...formData, system_prompt_override: e.target.value })}
              />
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t sticky bottom-0 z-10 flex gap-3 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)]" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
          <button 
            type="button"
            onClick={onClose}
            className="flex-1 py-3 rounded-xl border text-sm font-bold hover:bg-slate-50 transition-all"
            style={{ color: 'var(--color-text-main)', borderColor: 'var(--color-border)' }}
          >
            Cancel
          </button>
          <button 
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex-[2] py-3 rounded-xl text-white text-sm font-extrabold flex items-center justify-center gap-2 shadow-lg shadow-primary/20 hover:brightness-105 active:scale-95 transition-all"
            style={{ background: 'var(--color-primary)' }}
          >
            {isSaving && <span className="material-symbols-outlined text-base animate-spin">refresh</span>}
            {role ? 'Update Role' : 'Create Role'}
          </button>
        </div>
      </div>
    </div>
  );
}
