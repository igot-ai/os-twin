'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';
import { Button } from '@/components/ui/Button';

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
}

const MODEL_OPTIONS = [
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash' },
  { value: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro' },
  { value: 'anthropic:claude-opus-4-6', label: 'Claude 4.6 Opus' },
  { value: 'anthropic:claude-sonnet-4-6', label: 'Claude 4.6 Sonnet' },
];

interface PlanSettingsTabProps {
  planId: string;
}

export default function PlanSettingsTab({ planId }: PlanSettingsTabProps) {
  const [roles, setRoles] = useState<RoleConfig[]>([]);
  const [roleConfig, setRoleConfig] = useState<Record<string, { default_model: string }>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);

    Promise.all([
      apiGet<RoleConfig[]>(`/plans/${planId}/roles`).catch(() => []),
      apiGet<Record<string, { default_model: string }>>(`/plans/${planId}/config`).catch(() => ({})),
    ])
      .then(([rolesData, configData]) => {
        setRoles(Array.isArray(rolesData) ? rolesData : []);
        setRoleConfig(configData && typeof configData === 'object' ? configData as Record<string, { default_model: string }> : {});
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

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await apiPost(`/plans/${planId}/config`, roleConfig);
      setSaveStatus('Saved');
      setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      setSaveStatus('Error saving');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
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
          Customize models for each role. These take precedence over global settings.
        </p>
      </div>

      {roles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">group</span>
          <p className="text-sm text-text-muted">No roles defined for this plan.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {roles.map((role) => (
            <div key={role.name} className="bg-surface border border-border rounded-xl p-4">
              <div className="text-sm font-semibold text-text-main">{role.name}</div>
              <p className="text-xs text-text-muted mt-1 line-clamp-2">{role.description}</p>
              <div className="mt-3">
                <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1">
                  Model
                </label>
                <select
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                  value={roleConfig[role.name]?.default_model || role.default_model}
                  onChange={(e) => updateRoleModel(role.name, e.target.value)}
                >
                  {MODEL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}
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
