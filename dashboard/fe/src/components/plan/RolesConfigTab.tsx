'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { apiGet, apiPost, apiPut } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';
import { useSkills } from '@/hooks/use-skills';

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
  skill_refs?: string[];
}

interface RoleOverride {
  default_model: string;
  skill_refs?: string[];
}

const MODEL_OPTIONS = [
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { value: 'anthropic:claude-opus-4-6', label: 'Claude 4.6 Opus' },
  { value: 'anthropic:claude-sonnet-4-6', label: 'Claude 4.6 Sonnet' },
];

function SkillPicker({ 
  attachedSkills, 
  allSkills, 
  onAttach, 
  onDetach 
}: { 
  attachedSkills: string[]; 
  allSkills: { name: string; description: string }[]; 
  onAttach: (name: string) => void; 
  onDetach: (name: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const available = allSkills.filter(
    s => !attachedSkills.includes(s.name) && 
         (search === '' || s.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="mt-3">
      <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1.5">
        Skills
      </label>

      {/* Attached skill chips */}
      <div className="flex flex-wrap gap-1.5 mb-2 min-h-[24px]">
        {attachedSkills.length === 0 && (
          <span className="text-[10px] text-text-faint italic">No skills attached</span>
        )}
        {attachedSkills.map(name => (
          <span
            key={name}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-bold"
          >
            <span className="material-symbols-outlined text-[12px]">extension</span>
            {name}
            <button
              onClick={() => onDetach(name)}
              className="ml-0.5 hover:text-danger transition-colors"
              title={`Remove ${name}`}
            >
              <span className="material-symbols-outlined text-[12px]">close</span>
            </button>
          </span>
        ))}
      </div>

      {/* Add skill dropdown */}
      <div ref={ref} className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-dashed border-border text-[11px] text-text-muted hover:border-primary hover:text-primary transition-all"
        >
          <span className="material-symbols-outlined text-[14px]">add</span>
          Add skill
        </button>

        {isOpen && (
          <div className="absolute z-50 top-full mt-1 w-full bg-surface border border-border rounded-lg shadow-xl max-h-52 overflow-hidden flex flex-col">
            <div className="p-2 border-b border-border">
              <input
                type="text"
                placeholder="Search skills..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary/30 text-text-main placeholder:text-text-faint"
                autoFocus
              />
            </div>
            <div className="overflow-y-auto custom-scrollbar">
              {available.length === 0 ? (
                <div className="px-3 py-4 text-center text-[11px] text-text-faint">
                  {search ? 'No matching skills' : 'All skills attached'}
                </div>
              ) : (
                available.map(skill => (
                  <button
                    key={skill.name}
                    onClick={() => { onAttach(skill.name); setSearch(''); }}
                    className="w-full px-3 py-2 text-left hover:bg-surface-hover flex items-center gap-2.5 transition-colors"
                  >
                    <span className="material-symbols-outlined text-text-faint text-[16px]">extension</span>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-text-main truncate">{skill.name}</div>
                      <div className="text-[10px] text-text-faint truncate">{skill.description}</div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RolesConfigTab() {
  const { planId, planContent, epics } = usePlanContext();
  const { skills = [], isLoading: skillsLoading } = useSkills();
  const [roles, setRoles] = useState<RoleConfig[]>([]);
  const [roleConfig, setRoleConfig] = useState<Record<string, RoleOverride>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isOverridesExpanded, setIsOverridesExpanded] = useState(true);

  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    Promise.all([
      apiGet<RoleConfig[]>(`/plans/${planId}/roles`).catch(() => []),
      apiGet<Record<string, RoleOverride>>(`/plans/${planId}/config`).catch(() => ({})),
    ])
      .then(([rolesData, configData]) => {
        setRoles(Array.isArray(rolesData) ? rolesData : []);
        setRoleConfig(configData && typeof configData === 'object' ? configData as Record<string, RoleOverride> : {});
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load settings');
      })
      .finally(() => setIsLoading(false));
  }, [planId]);

  const updateRoleModel = useCallback((roleName: string, model: string) => {
    setRoleConfig((prev) => ({
      ...prev,
      [roleName]: { ...prev[roleName], default_model: model },
    }));
  }, []);

  const attachSkillToRole = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = [...(existing.skill_refs || [])];
      if (!refs.includes(skillName)) refs.push(skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs } };
    });
  }, []);

  const detachSkillFromRole = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = (existing.skill_refs || []).filter(s => s !== skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs } };
    });
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      // Save each role's config individually via PUT endpoint
      const promises = roles.map(role => {
        const cfg = roleConfig[role.name];
        if (!cfg) return Promise.resolve();
        return apiPut(`/plans/${planId}/roles/${role.name}/config`, {
          default_model: cfg.default_model || undefined,
          skill_refs: cfg.skill_refs || [],
        });
      });
      await Promise.all(promises);
      setSaveStatus('Saved');
      setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      setSaveStatus('Error saving');
    } finally {
      setIsSaving(false);
    }
  };

  // Parse Roles from planContent
  const parsedEpicRoles = useMemo(() => {
    const rolesMap: Record<string, string[]> = {};
    if (!planContent) return rolesMap;

    const sections = planContent.split(/^(?=### (?:EPIC|TASK)-)/m);
    sections.forEach(section => {
      const match = section.match(/^### ((?:EPIC|TASK)-\d+)/);
      if (match) {
        const id = match[1];
        const rolesMatch = section.match(/^Roles:\s*(.+)$/m);
        if (rolesMatch) {
          rolesMap[id] = rolesMatch[1].split(',').map(r => r.trim());
        }
      }
    });
    return rolesMap;
  }, [planContent]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar space-y-8">
      {/* Roles Assignment Section */}
      <section>
        <div className="mb-4">
          <h2 className="text-sm font-bold text-text-main uppercase tracking-wider">Epic Assignments</h2>
          <p className="text-xs text-text-muted mt-1">
            Roles assigned to each EPIC in the plan markdown.
          </p>
        </div>

        <div className="space-y-3">
          {epics && epics.length > 0 ? (
            epics.map((epic) => (
              <div key={epic.epic_ref} className="bg-surface border border-border rounded-xl p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-text-main">{epic.epic_ref} — {epic.title}</div>
                  <div className="flex gap-2 mt-2">
                    {parsedEpicRoles[epic.epic_ref] ? (
                      parsedEpicRoles[epic.epic_ref].map(role => (
                        <span key={role} className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary uppercase">
                          {role}
                        </span>
                      ))
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-border text-text-faint uppercase">
                        {epic.role || 'No role assigned'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 border border-dashed border-border rounded-xl">
              <p className="text-sm text-text-muted">No epics found in this plan.</p>
            </div>
          )}
        </div>
      </section>

      {/* Model & Skills Overrides Section */}
      <section className="border-t border-border pt-8">
        <button 
          onClick={() => setIsOverridesExpanded(!isOverridesExpanded)}
          className="w-full flex items-center justify-between mb-4 group"
        >
          <div className="text-left">
            <h2 className="text-sm font-bold text-text-main uppercase tracking-wider">Role Configuration</h2>
            <p className="text-xs text-text-muted mt-1">
              Customize models and attach skills for each role.
            </p>
          </div>
          <span className={`material-symbols-outlined transition-transform duration-200 ${isOverridesExpanded ? 'rotate-180' : ''}`}>
            expand_more
          </span>
        </button>

        {isOverridesExpanded && (
          <div className="space-y-6">
            {roles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center bg-surface/50 rounded-xl border border-dashed border-border">
                <span className="material-symbols-outlined text-3xl text-text-faint mb-2">group</span>
                <p className="text-xs text-text-muted">No roles defined for this plan.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {roles.map((role) => {
                  const cfg = roleConfig[role.name] || {};
                  const attachedSkills = cfg.skill_refs || role.skill_refs || [];
                  return (
                    <div key={role.name} className="bg-surface border border-border rounded-xl p-4">
                      <div className="text-sm font-semibold text-text-main">{role.name}</div>
                      <p className="text-xs text-text-muted mt-1 line-clamp-2">{role.description}</p>
                      
                      {/* Model selector */}
                      <div className="mt-3">
                        <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                          Model
                        </label>
                        <select
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                          value={cfg.default_model || role.default_model}
                          onChange={(e) => updateRoleModel(role.name, e.target.value)}
                        >
                          {MODEL_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Skill picker */}
                      <SkillPicker
                        attachedSkills={attachedSkills}
                        allSkills={skills}
                        onAttach={(name) => attachSkillToRole(role.name, name)}
                        onDetach={(name) => detachSkillFromRole(role.name, name)}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button variant="primary" size="sm" onClick={handleSave} isLoading={isSaving}>
                Save Configuration
              </Button>
              {saveStatus && (
                <span className={`text-xs font-medium ${saveStatus === 'Saved' ? 'text-success' : 'text-danger'}`}>
                  {saveStatus}
                </span>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
