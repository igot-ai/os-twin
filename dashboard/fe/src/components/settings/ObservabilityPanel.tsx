'use client';

import { ProvenanceChip } from './ProvenanceChip';
import type { ObservabilitySettings } from '@/types/settings';

export interface ObservabilityPanelProps {
  observability: ObservabilitySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<ObservabilitySettings>) => void;
}

export function ObservabilityPanel({ observability, provenance = {}, onUpdate }: ObservabilityPanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Log Level
        </label>
        <select
          value={observability.log_level}
          onChange={(e) => onUpdate({ log_level: e.target.value as ObservabilitySettings['log_level'] })}
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        >
          <option value="debug">Debug</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
        {provenance.log_level && <ProvenanceChip source={provenance.log_level} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Broadcast Verbosity
        </label>
        <select
          value={observability.broadcast_verbosity}
          onChange={(e) => onUpdate({ broadcast_verbosity: e.target.value as ObservabilitySettings['broadcast_verbosity'] })}
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        >
          <option value="minimal">Minimal</option>
          <option value="normal">Normal</option>
          <option value="verbose">Verbose</option>
        </select>
        {provenance.broadcast_verbosity && <ProvenanceChip source={provenance.broadcast_verbosity} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Trace Enabled
        </label>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={observability.trace_enabled}
              onChange={(e) => onUpdate({ trace_enabled: e.target.checked })}
              className="sr-only"
            />
            <div
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{
                background: observability.trace_enabled ? '#2563eb' : '#94a3b8',
              }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                style={{
                  left: observability.trace_enabled ? '22px' : '2px',
                }}
              />
            </div>
          </label>
          <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>
            {observability.trace_enabled ? 'Enabled' : 'Disabled'}
          </span>
          {provenance.trace_enabled && <ProvenanceChip source={provenance.trace_enabled} />}
        </div>
      </div>
    </div>
  );
}
