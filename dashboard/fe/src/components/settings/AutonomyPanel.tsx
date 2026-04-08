'use client';

import { ProvenanceChip } from './ProvenanceChip';
import type { AutonomySettings } from '@/types/settings';

export interface AutonomyPanelProps {
  autonomy: AutonomySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<AutonomySettings>) => void;
}

export function AutonomyPanel({ autonomy, provenance = {}, onUpdate }: AutonomyPanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Idle Explorer
        </label>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autonomy.idle_explore_enabled}
              onChange={(e) => onUpdate({ idle_explore_enabled: e.target.checked })}
              className="sr-only"
            />
            <div
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{
                background: autonomy.idle_explore_enabled ? '#2563eb' : '#94a3b8',
              }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                style={{
                  left: autonomy.idle_explore_enabled ? '22px' : '2px',
                }}
              />
            </div>
          </label>
          <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>
            {autonomy.idle_explore_enabled ? 'Enabled' : 'Disabled'}
          </span>
          {provenance.idle_explore_enabled && (
            <ProvenanceChip source={provenance.idle_explore_enabled} />
          )}
        </div>
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Interval (seconds)
        </label>
        <input
          type="number"
          value={autonomy.interval}
          onChange={(e) => onUpdate({ interval: parseInt(e.target.value, 10) || 1800 })}
          min={60}
          max={86400}
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        />
        {provenance.interval && <ProvenanceChip source={provenance.interval} />}
        <p className="text-[9px] mt-1 text-slate-500">
          Time between autonomous exploration cycles (60-86400 seconds)
        </p>
      </div>
    </div>
  );
}
