'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { apiGet, apiPut } from '@/lib/api-client';
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

interface RolesApiResponse {
  role_defaults: RoleConfig[];
  attached_skills?: string[];
}

const MODEL_OPTIONS = [
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { value: 'anthropic:claude-opus-4-6', label: 'Claude 4.6 Opus' },
  { value: 'anthropic:claude-sonnet-4-6', label: 'Claude 4.6 Sonnet' },
];

// ── SkillPicker ─────────────────────────────────────────────────

function SkillPicker({
  attachedSkills,
  allSkills,
  onAttach,
  onDetach,
}: {
  attachedSkills: string[];
  allSkills: { name: string; description: string }[];
  onAttach: (name: string) => void;
  onDetach: (name: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const available = allSkills.filter(
    (s) =>
      !attachedSkills.includes(s.name) &&
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
        {attachedSkills.map((name) => (
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
                onChange={(e) => setSearch(e.target.value)}
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
                available.map((skill) => (
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

// ── Main Component ──────────────────────────────────────────────

export default function RolesConfigTab() {
  const { planId } = usePlanContext();
  const { skills = [], isLoading: skillsLoading } = useSkills();
  const [roles, setRoles] = useState<RoleConfig[]>([]);
  const [roleConfig, setRoleConfig] = useState<Record<string, RoleOverride>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    Promise.all([
      apiGet<RolesApiResponse>(`/plans/${planId}/roles`).catch(() => ({ role_defaults: [] })),
      apiGet<Record<string, RoleOverride>>(`/plans/${planId}/config`).catch(() => ({})),
    ])
      .then(([rolesResp, configData]) => {
        // API returns { role_defaults: [...], ... } — extract the array
        const rolesArray = rolesResp?.role_defaults ?? [];
        setRoles(Array.isArray(rolesArray) ? rolesArray : []);
        setRoleConfig(
          configData && typeof configData === 'object'
            ? (configData as Record<string, RoleOverride>)
            : {}
        );
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

  const attachSkill = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = [...(existing.skill_refs || [])];
      if (!refs.includes(skillName)) refs.push(skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs } };
    });
  }, []);

  const detachSkill = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = (existing.skill_refs || []).filter((s) => s !== skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs } };
    });
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const promises = roles.map((role) => {
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
    } catch {
      setSaveStatus('Error saving');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading || skillsLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-6">
        <span className="material-symbols-outlined text-danger text-3xl mb-2">error</span>
        <p className="text-sm text-text-muted">{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar">
      <div className="mb-6">
        <h2 className="text-sm font-bold text-text-main uppercase tracking-wider">Role Overrides</h2>
        <p className="text-xs text-text-muted mt-1">
          Customize models and skills for each role. These take precedence over global settings.
        </p>
      </div>

      {roles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">group</span>
          <p className="text-sm text-text-muted">No roles defined for this plan.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {roles.map((role) => {
            const cfg = roleConfig[role.name] || {};
            const attached = cfg.skill_refs || role.skill_refs || [];
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
                  attachedSkills={attached}
                  allSkills={skills}
                  onAttach={(name) => attachSkill(role.name, name)}
                  onDetach={(name) => detachSkill(role.name, name)}
                />
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-6 flex items-center gap-3">
        <Button variant="primary" size="sm" onClick={handleSave} isLoading={isSaving}>
          Save Config
        </Button>
        {saveStatus && (
          <span className={`text-xs font-medium ${saveStatus === 'Saved' ? 'text-success' : 'text-danger'}`}>
            {saveStatus}
          </span>
        )}
      </div>
    </div>
  );
}
