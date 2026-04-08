'use client';

import { ProvenanceChip } from './ProvenanceChip';
import { ModelSelect } from './ModelSelect';
import { useConfiguredModels } from '@/hooks/use-configured-models';
import type { RoleSettings } from '@/types/settings';

export interface RolesPanelProps {
  roles: Record<string, RoleSettings>;
  provenance?: Record<string, Record<string, string>>;
  onUpdate: (role: string, value: Partial<RoleSettings>) => void;
  models: string[];
}

export function RolesPanel({ roles, provenance = {}, onUpdate, models }: RolesPanelProps) {
  const { allModels, providers } = useConfiguredModels();
  const roleEntries = Object.entries(roles);

  // Use dynamic models if available, fallback to flat string list
  const displayModels = allModels.length > 0
    ? allModels
    : models.map((m) => ({ id: m, label: m }));

  if (roleEntries.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        <span className="material-symbols-outlined text-4xl mb-2 block">person</span>
        <p className="text-xs">No roles configured</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {roleEntries.map(([roleName, roleSettings]) => {
        const roleProv = provenance[roleName] || {};

        return (
          <div
            key={roleName}
            className="rounded-lg border p-4"
            style={{
              background: '#ffffff',
              borderColor: '#e2e8f0',
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold uppercase" style={{ color: '#0f172a' }}>
                {roleName}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                  Default Model
                </label>
                <ModelSelect
                  value={roleSettings.default_model || ''}
                  onChange={(model) => onUpdate(roleName, { default_model: model })}
                  models={displayModels}
                  providers={providers}
                  grouped={false}
                  placeholder="Select model"
                />
                {roleProv.default_model && <ProvenanceChip source={roleProv.default_model} />}
              </div>

              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                  Temperature
                </label>
                <input
                  type="number"
                  value={roleSettings.temperature ?? 0.7}
                  onChange={(e) => onUpdate(roleName, { temperature: parseFloat(e.target.value) || 0.7 })}
                  min={0}
                  max={2}
                  step={0.1}
                  className="w-full px-3 py-2 rounded-md text-xs font-mono"
                  style={{
                    background: '#f1f5f9',
                    border: '1px solid #e2e8f0',
                    color: '#0f172a',
                  }}
                />
                {roleProv.temperature && <ProvenanceChip source={roleProv.temperature} />}
              </div>

              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                  Timeout (seconds)
                </label>
                <input
                  type="number"
                  value={roleSettings.timeout_seconds ?? 300}
                  onChange={(e) => onUpdate(roleName, { timeout_seconds: parseInt(e.target.value, 10) || 300 })}
                  min={1}
                  className="w-full px-3 py-2 rounded-md text-xs font-mono"
                  style={{
                    background: '#f1f5f9',
                    border: '1px solid #e2e8f0',
                    color: '#0f172a',
                  }}
                />
                {roleProv.timeout_seconds && <ProvenanceChip source={roleProv.timeout_seconds} />}
              </div>

              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                  Max Retries
                </label>
                <input
                  type="number"
                  value={roleSettings.max_retries ?? 3}
                  onChange={(e) => onUpdate(roleName, { max_retries: parseInt(e.target.value, 10) || 3 })}
                  min={0}
                  max={10}
                  className="w-full px-3 py-2 rounded-md text-xs font-mono"
                  style={{
                    background: '#f1f5f9',
                    border: '1px solid #e2e8f0',
                    color: '#0f172a',
                  }}
                />
                {roleProv.max_retries && <ProvenanceChip source={roleProv.max_retries} />}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
