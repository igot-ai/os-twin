'use client';

import React from 'react';
import { Epic } from '@/types';

interface RoleOverride {
  id: string;
  name: string;
  provider?: string;
  version?: string;
  old_version?: string;
  skill_refs?: string[];
  isOverridden: boolean;
}

interface EpicWithRoles extends Epic {
  roles?: RoleOverride[];
}

interface RoleOverridesPanelProps {
  epic: Epic;
}

export default function RoleOverridesPanel({ epic }: RoleOverridesPanelProps) {
  // Use epic.roles if available, or fallback to mock
  const roles = (epic as EpicWithRoles).roles || [
    {
      id: 'da-001',
      name: 'Data Analyst',
      provider: 'gpt',
      version: 'gpt-4o (Large)',
      old_version: 'gpt-4o-mini',
      skill_refs: ['WebBrowsing', 'FileSearch'],
      isOverridden: true
    },
    {
      id: 'cw-001',
      name: 'Copywriter',
      isOverridden: false
    }
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Panel Header */}
      <div className="p-4 border-b border-border bg-surface-hover/30 shrink-0">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">settings_input_component</span> Role Overrides
        </h2>
      </div>

      {/* Role Overrides Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        {roles.map((role) => (
          <div 
            key={role.id} 
            className={`p-3 rounded border ${
              role.isOverridden 
                ? 'border-primary/30 bg-primary-muted' 
                : 'border-border bg-surface'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-text-main">{role.name}</span>
              <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                role.isOverridden 
                  ? 'bg-primary text-white' 
                  : 'bg-surface-hover text-text-muted'
              }`}>
                {role.isOverridden ? 'Overridden' : 'Inherited'}
              </span>
            </div>

            {role.isOverridden ? (
              <div className="space-y-2">
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-faint uppercase font-bold tracking-tighter">Model</span>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-text-faint line-through">{role.old_version || 'gpt-4o-mini'}</span>
                    <span className="text-primary font-bold">{role.version || 'gpt-4o (Large)'}</span>
                  </div>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-faint uppercase font-bold tracking-tighter">Skills</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(role.skill_refs || []).map((skill: string) => (
                      <span key={skill} className="px-1.5 py-0.5 bg-surface border border-primary/20 text-primary text-[9px] rounded">
                        + {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-text-muted">Using default Plan-level configurations.</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
