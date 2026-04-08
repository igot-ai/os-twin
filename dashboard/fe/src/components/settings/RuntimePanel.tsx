'use client';

import { ProvenanceChip } from './ProvenanceChip';
import type { RuntimeSettings } from '@/types/settings';

export interface RuntimePanelProps {
  runtime: RuntimeSettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<RuntimeSettings>) => void;
}

export function RuntimePanel({ runtime, provenance = {}, onUpdate }: RuntimePanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Poll Interval
        </label>
        <input
          type="range"
          min={1}
          max={300}
          value={runtime.poll_interval}
          onChange={(e) => onUpdate({ poll_interval: parseInt(e.target.value, 10) })}
          className="w-full h-2 rounded-lg appearance-none cursor-pointer"
          style={{ background: '#f1f5f9' }}
        />
        <div className="flex justify-between text-[9px] mt-1 text-slate-500">
          <span>1s</span>
          <span className="font-mono font-bold" style={{ color: '#0f172a' }}>
            {runtime.poll_interval}s
          </span>
          <span>300s</span>
        </div>
        {provenance.poll_interval && <ProvenanceChip source={provenance.poll_interval} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Max Concurrent Rooms
        </label>
        <input
          type="range"
          min={1}
          max={500}
          value={runtime.max_concurrent_rooms}
          onChange={(e) => onUpdate({ max_concurrent_rooms: parseInt(e.target.value, 10) })}
          className="w-full h-2 rounded-lg appearance-none cursor-pointer"
          style={{ background: '#f1f5f9' }}
        />
        <div className="flex justify-between text-[9px] mt-1 text-slate-500">
          <span>1</span>
          <span className="font-mono font-bold" style={{ color: '#0f172a' }}>
            {runtime.max_concurrent_rooms}
          </span>
          <span>500</span>
        </div>
        {provenance.max_concurrent_rooms && <ProvenanceChip source={provenance.max_concurrent_rooms} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Auto Approve Tools
        </label>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={runtime.auto_approve_tools}
              onChange={(e) => onUpdate({ auto_approve_tools: e.target.checked })}
              className="sr-only"
            />
            <div
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{
                background: runtime.auto_approve_tools ? '#2563eb' : '#94a3b8',
              }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                style={{
                  left: runtime.auto_approve_tools ? '22px' : '2px',
                }}
              />
            </div>
          </label>
          <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>
            {runtime.auto_approve_tools ? 'Enabled' : 'Disabled'}
          </span>
          {provenance.auto_approve_tools && <ProvenanceChip source={provenance.auto_approve_tools} />}
        </div>
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Dynamic Pipelines
        </label>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={runtime.dynamic_pipelines}
              onChange={(e) => onUpdate({ dynamic_pipelines: e.target.checked })}
              className="sr-only"
            />
            <div
              className="relative w-10 h-5 rounded-full transition-colors"
              style={{
                background: runtime.dynamic_pipelines ? '#2563eb' : '#94a3b8',
              }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                style={{
                  left: runtime.dynamic_pipelines ? '22px' : '2px',
                }}
              />
            </div>
          </label>
          <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>
            {runtime.dynamic_pipelines ? 'Enabled' : 'Disabled'}
          </span>
          {provenance.dynamic_pipelines && <ProvenanceChip source={provenance.dynamic_pipelines} />}
        </div>
      </div>
    </div>
  );
}
