'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { apiGet, apiPut } from '@/lib/api-client';
import { useSkills } from '@/hooks/use-skills';
import { useConfiguredModels } from '@/hooks/use-configured-models';
import { ProvenanceChip } from '@/components/settings/ProvenanceChip';
import { ModelSelect } from '@/components/settings/ModelSelect';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import { useSharedWebSocket } from '@/components/providers/WebSocketProvider';
import RoleSkillManager from './RoleSkillManager';

import type { RoleSettings } from '@/types/settings';

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
  skill_refs?: string[];
}

interface ModelInfo {
  id: string;
  label?: string;
  context_window: string;
  tier: string;
}

type ModelsRegistry = Record<string, ModelInfo[]>;

const AUTOSAVE_DELAY = 800; // ms debounce

export default function RolesConfigTab() {
  const { planId } = usePlanContext();
  const { skills = [], isLoading: skillsLoading } = useSkills();
  const { allModels: configuredModels, providers: configuredProviders } = useConfiguredModels();
  const { addToast } = useNotificationStore();

  const [roles, setRoles] = useState<RoleConfig[]>([]);
  const [effectiveRoleNames, setEffectiveRoleNames] = useState<string[]>([]);
  const [modelsRegistry, setModelsRegistry] = useState<ModelsRegistry>({});
  const [roleConfig, setRoleConfig] = useState<Record<string, RoleSettings>>({});
  const [effectiveSettings, setEffectiveSettings] = useState<Record<string, { effective: Record<string, unknown>; provenance: Record<string, string> }>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPrompts, setExpandedPrompts] = useState<Record<string, boolean>>({});
  const [savingRoles, setSavingRoles] = useState<Set<string>>(new Set());

  // Debounce timers per role
  const saveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  // Track the latest config to avoid stale closures
  const latestConfig = useRef(roleConfig);
  latestConfig.current = roleConfig;

  // ── Fetch roles + registry on mount ────────────────────────────────
  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    Promise.all([
      apiGet<{ role_defaults: RoleConfig[]; effective_roles: string[] }>(`/plans/${planId}/roles`).catch(() => ({ role_defaults: [], effective_roles: [] })),
      apiGet<ModelsRegistry>('/models/registry').catch(() => ({})),
    ])
      .then(([rolesResp, registry]) => {
        const rolesArray = rolesResp?.role_defaults ?? [];
        const effective = rolesResp?.effective_roles ?? [];
        setRoles(Array.isArray(rolesArray) ? rolesArray : []);
        setEffectiveRoleNames(Array.isArray(effective) ? effective : []);
        setModelsRegistry(registry && typeof registry === 'object' ? (registry as ModelsRegistry) : ({} as ModelsRegistry));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load settings');
      })
      .finally(() => setIsLoading(false));
  }, [planId]);

  // ── Fetch effective settings for each role ─────────────────────────
  const fetchEffective = useCallback(async () => {
    if (roles.length === 0 || !planId) return;

    const results: Record<string, { effective: Record<string, unknown>; provenance: Record<string, string> }> = {};
    const configData: Record<string, RoleSettings> = {};

    await Promise.all(
      roles.map(async (role) => {
        try {
          const params = new URLSearchParams({ role: role.name, plan_id: planId });
          const data = await apiGet<{ effective: Record<string, unknown>; provenance: Record<string, string> }>(
            `/settings/effective?${params.toString()}`
          );
          results[role.name] = data;
          configData[role.name] = {
            default_model: data.effective.default_model as string | undefined,
            temperature: data.effective.temperature as number | undefined,
            timeout_seconds: data.effective.timeout_seconds as number | undefined,
            max_retries: data.effective.max_retries as number | undefined,
            budget_tokens_max: data.effective.budget_tokens_max as number | undefined,
            system_prompt_override: data.effective.system_prompt_override as string | undefined,
            skill_refs: (data.effective.skill_refs as string[]) || [],
            disabled_skills: (data.effective.disabled_skills as string[]) || [],
          };
        } catch {
          results[role.name] = { effective: {}, provenance: {} };
          configData[role.name] = {};
        }
      })
    );

    setEffectiveSettings(results);
    setRoleConfig(configData);
  }, [roles, planId]);

  useEffect(() => { fetchEffective(); }, [fetchEffective]);

  // ── WebSocket refresh ──────────────────────────────────────────────
  const { lastMessage } = useSharedWebSocket();


  useEffect(() => {
    if (lastMessage && (lastMessage.type === 'settings_updated' || lastMessage.event === 'settings_updated')) {
      fetchEffective();
    }
  }, [lastMessage, fetchEffective]);

  // ── Autosave: persist a single role's config ───────────────────────
  const saveRole = useCallback(async (roleName: string) => {
    const cfg = latestConfig.current[roleName];
    if (!cfg || !planId) return;

    const payload: Record<string, unknown> = {};
    if (cfg.default_model !== undefined) payload.default_model = cfg.default_model;
    if (cfg.temperature !== undefined) payload.temperature = cfg.temperature;
    if (cfg.timeout_seconds !== undefined) payload.timeout_seconds = cfg.timeout_seconds;
    if (cfg.max_retries !== undefined) payload.max_retries = cfg.max_retries;
    if (cfg.budget_tokens_max !== undefined) payload.budget_tokens_max = cfg.budget_tokens_max;
    if (cfg.system_prompt_override !== undefined) payload.system_prompt_override = cfg.system_prompt_override;
    if (cfg.skill_refs !== undefined) payload.skill_refs = cfg.skill_refs;
    if (cfg.disabled_skills !== undefined) payload.disabled_skills = cfg.disabled_skills;

    setSavingRoles((prev) => new Set(prev).add(roleName));
    try {
      await apiPut(`/settings/plan/${planId}/role/${roleName}`, payload);
    } catch {
      addToast({ type: 'error', title: 'Save failed', message: `Could not save ${roleName} settings`, autoDismiss: true });
    } finally {
      setSavingRoles((prev) => { const next = new Set(prev); next.delete(roleName); return next; });
    }
  }, [planId, addToast]);

  // ── Debounced save trigger ─────────────────────────────────────────
  const scheduleSave = useCallback((roleName: string) => {
    if (saveTimers.current[roleName]) clearTimeout(saveTimers.current[roleName]);
    saveTimers.current[roleName] = setTimeout(() => { saveRole(roleName); }, AUTOSAVE_DELAY);
  }, [saveRole]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => { Object.values(saveTimers.current).forEach(clearTimeout); };
  }, []);

  // ── Field update + autosave ────────────────────────────────────────
  const updateRoleField = useCallback((roleName: string, field: keyof RoleSettings, value: unknown) => {
    setRoleConfig((prev) => ({
      ...prev,
      [roleName]: { ...prev[roleName], [field]: value },
    }));
    scheduleSave(roleName);
  }, [scheduleSave]);

  const attachSkill = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = [...(existing.skill_refs || [])];
      if (!refs.includes(skillName)) refs.push(skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs } };
    });
    scheduleSave(roleName);
  }, [scheduleSave]);

  const detachSkill = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const refs = (existing.skill_refs || []).filter((s) => s !== skillName);
      const disabled = (existing.disabled_skills || []).filter((s) => s !== skillName);
      return { ...prev, [roleName]: { ...existing, skill_refs: refs, disabled_skills: disabled } };
    });
    scheduleSave(roleName);
  }, [scheduleSave]);

  const toggleSkillDisabled = useCallback((roleName: string, skillName: string) => {
    setRoleConfig((prev) => {
      const existing = prev[roleName] || {};
      const disabled = existing.disabled_skills || [];
      const updated = disabled.includes(skillName)
        ? disabled.filter((s) => s !== skillName)
        : [...disabled, skillName];
      return { ...prev, [roleName]: { ...existing, disabled_skills: updated } };
    });
    scheduleSave(roleName);
  }, [scheduleSave]);

  // ── Render ─────────────────────────────────────────────────────────
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
          Customize models and parameters for each role. Changes are saved automatically.
        </p>
        {effectiveRoleNames.length > 0 && (
          <div className="mt-2 flex items-center gap-2 text-[10px] text-text-faint">
            <span className="material-symbols-outlined text-sm">description</span>
            Showing {roles.length} role{roles.length !== 1 ? 's' : ''} declared in plan:
            <span className="font-semibold text-text-muted">{effectiveRoleNames.join(', ')}</span>
          </div>
        )}
      </div>

      {roles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">group</span>
          <p className="text-sm text-text-muted">No roles declared in the plan epics.</p>
          <p className="text-xs text-text-faint mt-1">Add <code className="bg-surface-hover px-1 rounded">Roles: @engineer, @qa</code> to your epic markdown.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {roles.map((role) => {
            const cfg = roleConfig[role.name] || {};
            const provenance = effectiveSettings[role.name]?.provenance || {};
            const attached = cfg.skill_refs || [];
            const isPromptExpanded = expandedPrompts[role.name] || false;
            const isSaving = savingRoles.has(role.name);

            return (
              <div key={role.name} className="bg-surface border border-border rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-semibold text-text-main">{role.name}</div>
                    <p className="text-xs text-text-muted mt-1 line-clamp-2">{role.description}</p>
                  </div>
                  {isSaving && (
                    <span className="material-symbols-outlined text-primary text-sm animate-spin">progress_activity</span>
                  )}
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                      Model
                    </label>
                    <ModelSelect
                      value={cfg.default_model || ''}
                      onChange={(model) => updateRoleField(role.name, 'default_model', model)}
                      models={configuredModels.length > 0 ? configuredModels : Object.values(modelsRegistry).flat().map((m) => ({ id: m.id, label: m.label || m.id, context_window: m.context_window, tier: m.tier }))}
                      providers={configuredProviders}
                      grouped={false}
                      placeholder="Select a model"
                    />
                    {provenance.default_model && (
                      <div className="mt-1">
                        <ProvenanceChip source={provenance.default_model} />
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                        Temperature
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={cfg.temperature ?? 1}
                          onChange={(e) => updateRoleField(role.name, 'temperature', parseFloat(e.target.value))}
                          className="flex-1 h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                        <span className="text-xs text-text-muted w-8 text-right">{cfg.temperature?.toFixed(1) ?? '1.0'}</span>
                      </div>
                      {provenance.temperature && (
                        <div className="mt-1">
                          <ProvenanceChip source={provenance.temperature} />
                        </div>
                      )}
                    </div>

                    <div>
                      <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                        Timeout (s)
                      </label>
                      <input
                        type="number"
                        min="60"
                        max="3600"
                        value={cfg.timeout_seconds ?? ''}
                        onChange={(e) => {
                          const val = parseInt(e.target.value);
                          if (!isNaN(val) && val >= 60 && val <= 3600) {
                            updateRoleField(role.name, 'timeout_seconds', val);
                          }
                        }}
                        placeholder="60-3600"
                        className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                      />
                      {provenance.timeout_seconds && (
                        <div className="mt-1">
                          <ProvenanceChip source={provenance.timeout_seconds} />
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                        Max Retries
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={cfg.max_retries ?? ''}
                        onChange={(e) => {
                          const val = parseInt(e.target.value);
                          if (!isNaN(val) && val >= 1 && val <= 10) {
                            updateRoleField(role.name, 'max_retries', val);
                          }
                        }}
                        placeholder="1-10"
                        className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                      />
                      {provenance.max_retries && (
                        <div className="mt-1">
                          <ProvenanceChip source={provenance.max_retries} />
                        </div>
                      )}
                    </div>
                  </div>

                  <div>
                    <button
                      onClick={() => setExpandedPrompts((prev) => ({ ...prev, [role.name]: !prev[role.name] }))}
                      className="flex items-center gap-1 text-[10px] font-bold text-text-faint uppercase tracking-wider hover:text-text-muted transition-colors"
                    >
                      <span className="material-symbols-outlined text-sm">
                        {isPromptExpanded ? 'expand_less' : 'expand_more'}
                      </span>
                      System Prompt Override
                    </button>
                    {isPromptExpanded && (
                      <div className="mt-2">
                        <textarea
                          maxLength={4000}
                          rows={4}
                          value={cfg.system_prompt_override ?? ''}
                          onChange={(e) => updateRoleField(role.name, 'system_prompt_override', e.target.value)}
                          placeholder="Override the default system prompt for this role..."
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none font-mono"
                        />
                        <div className="flex items-center justify-between mt-1">
                          {provenance.system_prompt_override && (
                            <ProvenanceChip source={provenance.system_prompt_override} />
                          )}
                          <span className="text-[10px] text-text-faint ml-auto">
                            {(cfg.system_prompt_override?.length || 0)}/4000
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-border">
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
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
