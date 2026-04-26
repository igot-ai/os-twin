'use client';

import { useMemo } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import { ModelSelect } from './ModelSelect';
import type { RuntimeSettings, ModelInfo } from '@/types/settings';

export interface RuntimePanelProps {
  runtime: RuntimeSettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<RuntimeSettings>) => void;
  allModels?: ModelInfo[];
}

export function RuntimePanel({ runtime, provenance = {}, onUpdate, allModels = [] }: RuntimePanelProps) {
  // Filter out embedding models from the master agent model picker
  const chatModels = useMemo(
    () => allModels.filter((m) => !m.id.toLowerCase().includes('embed')),
    [allModels],
  );

  return (
    <div className="space-y-8">
      {/* ── Master Agent Model ──────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">smart_toy</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Master Agent Model</h3>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <p className="text-[10px] text-slate-500 mb-3">
            The default LLM used by the master agent for plan refinement, brainstorming,
            and orchestration. All sub-systems (knowledge, memory) will also use their
            provider API key from the same vault when available.
          </p>
          <ModelSelect
            value={runtime.master_agent_model || ''}
            onChange={(model) => onUpdate({ master_agent_model: model })}
            models={chatModels}
            showTier={true}
            showContext={true}
            placeholder="— Use server default —"
          />
          {chatModels.length === 0 && (
            <p className="text-[10px] text-amber-600 mt-2">
              No providers configured — add one in Provider Config.
            </p>
          )}
          <p className="text-[10px] text-slate-400 mt-2">
            Currently effective:{' '}
            <code className="font-mono text-[10px] text-slate-600">
              {runtime.master_agent_model || '(server default)'}
            </code>
          </p>
        </div>
      </section>

      {/* ── Operational Settings ─────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-slate-500 text-lg">tune</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Operational Settings</h3>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-6">
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
              max={10000}
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
              <span>10000</span>
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
      </section>
    </div>
  );
}
