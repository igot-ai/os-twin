'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { apiGet, apiPut } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';
import { useSkills } from '@/hooks/use-skills';
import RoleSkillManager from './RoleSkillManager';

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
  skill_refs?: string[];
}

interface RoleOverride {
  default_model: string;
  skill_refs?: string[];
  disabled_skills?: string[];
}

interface RolesApiResponse {
  role_defaults: RoleConfig[];
  attached_skills?: string[];
}

const MODEL_OPTIONS = [
  { value: 'google-vertex/gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { value: 'google-vertex/gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { value: 'google-vertex/gemini-2.5-pro-preview-05-06', label: 'Gemini 2.5 Pro' },
  { value: 'google-vertex/gemini-2.5-flash-preview-05-20', label: 'Gemini 2.5 Flash' },
  { value: 'google-vertex/zai-org/glm-5-maas', label: 'GLM-5' },
  { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { value: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { value: 'gpt-4.1', label: 'GPT-4.1' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
  { value: 'o3', label: 'O3' },
  { value: 'o4-mini', label: 'O4 Mini' },
];

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
      const disabled = (existing.disabled_skills || []).filter((s) => s !== skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs, disabled_skills: disabled } };
    });
  }, []);

  const toggleSkillDisabled = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const disabled = existing.disabled_skills || [];
      const updated = disabled.includes(skillName)
        ? disabled.filter((s) => s !== skillName)
        : [...disabled, skillName];
      return { ...prev, [roleName]: { ...existing, disabled_skills: updated } };
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
          disabled_skills: cfg.disabled_skills || [],
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

                <RoleSkillManager
                  roleName={role.name}
                  overrides={{
                    skill_refs: attached,
                    disabled_skills: cfg.disabled_skills || [],
                  }}
                  allSkills={skills}
                  onToggleDisabled={(name) => toggleSkillDisabled(role.name, name)}
                  onRemove={(name) => detachSkill(role.name, name)}
                  onAdd={(name) => attachSkill(role.name, name)}
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
