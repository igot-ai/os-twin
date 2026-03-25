'use client';

import { useState, useMemo } from 'react';
import { Role, Skill } from '@/types';
import { mutate } from 'swr';
import { useModelRegistry } from '@/hooks/use-roles';
import TestConnectionButton from './TestConnectionButton';

interface RolesTableProps {
  roles: Role[];
  skills: Skill[];
  onEdit: (role: Role) => void;
  onAdd: () => void;
  isLoading?: boolean;
}

type SortKey = 'name' | 'provider' | 'temperature' | 'budget_tokens_max';
type SortDir = 'asc' | 'desc';

const providerBranding: Record<string, { color: string; label: string; icon: string }> = {
  claude: { color: '#D97706', label: 'Anthropic', icon: '🟡' },
  gpt: { color: '#10B981', label: 'OpenAI', icon: '🟢' },
  gemini: { color: '#6366F1', label: 'Google', icon: '🟣' },
  custom: { color: '#64748b', label: 'Custom', icon: '⚪' },
};

export default function RolesTable({ roles, skills, onEdit, onAdd, isLoading }: RolesTableProps) {
  const { registry } = useModelRegistry();
  const [sortConfig, setSortConfig] = useState<{ key: SortKey; dir: SortDir }>({ key: 'name', dir: 'asc' });

  const modelMetadata = useMemo(() => {
    if (!registry) return {};
    const meta: Record<string, { tier: string; context_window: string }> = {};
    Object.values(registry).flat().forEach(m => {
      meta[m.id] = { tier: m.tier, context_window: m.context_window };
    });
    return meta;
  }, [registry]);

  const sortedRoles = useMemo(() => {
    return [...roles].sort((a, b) => {
      const valA = a[sortConfig.key] || '';
      const valB = b[sortConfig.key] || '';
      if (valA < valB) return sortConfig.dir === 'asc' ? -1 : 1;
      if (valA > valB) return sortConfig.dir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [roles, sortConfig]);

  const toggleSort = (key: SortKey) => {
    setSortConfig(prev => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this role?')) return;
    try {
      const response = await fetch(`/api/roles/${id}`, { method: 'DELETE' });
      if (response.ok) {
        mutate('/api/roles');
      }
    } catch (error) {
      console.error('Failed to delete role:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-20 animate-pulse">
        <div className="w-12 h-12 rounded-full bg-surface-hover mb-4 flex items-center justify-center">
          <span className="material-symbols-outlined text-text-faint animate-spin" aria-hidden="true">refresh</span>
        </div>
        <p className="text-sm font-bold text-text-faint uppercase tracking-widest">Loading roles...</p>
      </div>
    );
  }

  if (roles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-20 text-center border-2 border-dashed rounded-2xl bg-surface-hover/30 border-border">
        <div className="w-16 h-16 rounded-2xl bg-surface shadow-sm mb-6 flex items-center justify-center">
          <span className="material-symbols-outlined text-3xl text-text-faint" aria-hidden="true">smart_toy</span>
        </div>
        <h3 className="text-xl font-extrabold text-text-main mb-2">No Roles Configured</h3>
        <p className="text-sm text-text-muted max-w-[320px] mb-8">
          Roles define how agents interact with LLMs and what skills they can utilize during plan execution.
        </p>
        <button 
          onClick={onAdd}
          className="flex items-center gap-2 px-6 py-3 rounded-xl text-white font-extrabold shadow-lg shadow-primary/20 hover:brightness-105 transition-all"
          style={{ background: 'var(--color-primary)' }}
          aria-label="Create First Role"
        >
          <span className="material-symbols-outlined text-xl" aria-hidden="true">add</span>
          Create First Role
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border overflow-hidden shadow-sm" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="sticky top-0 z-10 shadow-[0_1px_0_0_rgba(0,0,0,0.05)]" style={{ background: 'var(--color-surface)' }}>
              <th 
                className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest cursor-pointer hover:bg-slate-50 transition-colors group" 
                onClick={() => toggleSort('name')}
                style={{ color: 'var(--color-text-faint)' }}
              >
                <div className="flex items-center gap-1">
                  Role Identity
                  <span className={`material-symbols-outlined text-sm transition-opacity ${sortConfig.key === 'name' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
                    {sortConfig.dir === 'asc' ? 'expand_less' : 'expand_more'}
                  </span>
                </div>
              </th>
              <th 
                className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest cursor-pointer hover:bg-slate-50 transition-colors group" 
                onClick={() => toggleSort('provider')}
                style={{ color: 'var(--color-text-faint)' }}
              >
                <div className="flex items-center gap-1">
                  Model Binding
                  <span className={`material-symbols-outlined text-sm transition-opacity ${sortConfig.key === 'provider' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
                    {sortConfig.dir === 'asc' ? 'expand_less' : 'expand_more'}
                  </span>
                </div>
              </th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Skills</th>
              <th 
                className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest cursor-pointer hover:bg-slate-50 transition-colors group" 
                onClick={() => toggleSort('temperature')}
                style={{ color: 'var(--color-text-faint)' }}
              >
                <div className="flex items-center gap-1">
                  Sampling
                  <span className={`material-symbols-outlined text-sm transition-opacity ${sortConfig.key === 'temperature' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
                    {sortConfig.dir === 'asc' ? 'expand_less' : 'expand_more'}
                  </span>
                </div>
              </th>
              <th 
                className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest cursor-pointer hover:bg-slate-50 transition-colors group text-right" 
                onClick={() => toggleSort('budget_tokens_max')}
                style={{ color: 'var(--color-text-faint)' }}
              >
                <div className="flex items-center gap-1 justify-end">
                  Budget
                  <span className={`material-symbols-outlined text-sm transition-opacity ${sortConfig.key === 'budget_tokens_max' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
                    {sortConfig.dir === 'asc' ? 'expand_less' : 'expand_more'}
                  </span>
                </div>
              </th>
              <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest text-right" style={{ color: 'var(--color-text-faint)' }}>Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y" style={{ borderColor: 'var(--color-border-light)' }}>
            {sortedRoles.map((role) => {
              const pb = providerBranding[role.provider] || providerBranding.custom;
              const roleSkills = skills.filter((s) => role.skill_refs.includes(s.name));
              
              return (
                <tr
                  key={role.id}
                  className="hover:bg-slate-50/80 transition-all duration-200 group"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div 
                        className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-black text-white shadow-sm ring-2 ring-white" 
                        style={{ background: `linear-gradient(135deg, ${pb.color}, ${pb.color}dd)` }}
                      >
                        {role.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-sm font-extrabold capitalize text-slate-800">{role.name}</div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{role.id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{pb.icon}</span>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <div className="text-xs font-bold text-slate-700">{role.version}</div>
                          {modelMetadata[role.version] && (
                            <span className={`px-1.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-tighter ${
                              modelMetadata[role.version].tier === 'flagship' ? 'bg-indigo-100 text-indigo-600' : 
                              modelMetadata[role.version].tier === 'fast' ? 'bg-amber-100 text-amber-600' : 
                              'bg-slate-100 text-slate-500'
                            }`}>
                              {modelMetadata[role.version].tier}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] font-medium text-slate-400 uppercase tracking-widest">{pb.label}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1.5 max-w-[200px]">
                      {roleSkills.slice(0, 2).map((s) => (
                        <span
                          key={s.id}
                          className="px-2 py-0.5 rounded-full text-[10px] font-bold border"
                          style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)', borderColor: 'rgba(var(--color-primary-rgb), 0.1)' }}
                        >
                          {s.name}
                        </span>
                      ))}
                      {roleSkills.length > 2 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
                          +{roleSkills.length - 2}
                        </span>
                      )}
                      {roleSkills.length === 0 && (
                        <span className="text-[11px] text-slate-300 italic">No skills</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1.5 w-24">
                      <div className="flex items-center justify-between text-[10px] font-bold text-slate-500">
                        <span>{role.temperature}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden shadow-inner">
                        <div 
                          className="h-full transition-all duration-1000" 
                          style={{ 
                            width: `${(role.temperature / 2) * 100}%`, 
                            background: role.temperature <= 0.4 ? 'var(--color-primary)' : role.temperature <= 0.8 ? 'var(--color-warning)' : 'var(--color-danger)' 
                          }} 
                        />
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="text-sm font-mono font-bold text-slate-700">
                      {(role.budget_tokens_max / 1000).toFixed(0)}k
                    </div>
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Tokens</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <TestConnectionButton version={role.version} />
                      <button 
                        onClick={() => onEdit(role)}
                        className="p-2 hover:bg-primary/10 hover:text-primary rounded-lg transition-all"
                        title="Edit Role"
                      >
                        <span className="material-symbols-outlined text-lg">edit</span>
                      </button>
                      <button 
                        onClick={() => handleDelete(role.id)}
                        className="p-2 hover:bg-red-50 hover:text-red-500 rounded-lg transition-all"
                        title="Delete Role"
                      >
                        <span className="material-symbols-outlined text-lg">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
