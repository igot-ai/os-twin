'use client';

import { useEffect, useState } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import type {
  MemorySettings,
  MemoryVectorBackend,
} from '@/types/settings';

export interface MemoryPanelProps {
  memory: MemorySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<MemorySettings>) => void;
}

const VECTOR_BACKENDS = [
  { value: 'zvec', label: 'zvec', description: 'Lightweight HNSW vector store — recommended', icon: 'database' },
  { value: 'chroma', label: 'ChromaDB', description: 'Feature-rich vector database', icon: 'view_in_ar' },
];

const DEFAULTS = {
  vector_backend: 'zvec' as const,
  context_aware: true,
  context_aware_tree: false,
  max_links: 3,
  similarity_weight: 0.8,
  decay_half_life_days: 30,
  auto_sync: true,
  sync_interval_s: 60,
  conflict_resolution: 'last_modified',
  pool_idle_timeout_s: 300,
  pool_max_instances: 10,
  pool_eviction_policy: 'lru',
  pool_sync_interval_s: 60,
};

export function MemoryPanel({ memory, provenance = {}, onUpdate }: MemoryPanelProps) {
  const [poolHealth, setPoolHealth] = useState<any>(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await fetch('/api/memory-pool/health');
        if (res.ok) setPoolHealth(await res.json());
      } catch { /* ignore */ }
    };
    fetchInfo();
    const interval = setInterval(fetchInfo, 10000);
    return () => clearInterval(interval);
  }, []);

  const effective = { ...DEFAULTS, ...memory };

  const inputStyle = {
    background: '#f1f5f9',
    border: '1px solid #e2e8f0',
    color: '#0f172a',
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <p className="text-sm text-on-surface-variant">
          Memory system configuration. LLM and embedding models are configured in{' '}
          <strong>Provider Config</strong> and routed through the centralized AI gateway.
        </p>
      </div>

      {/* Section 1: AI Gateway Status */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">hub</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">AI Gateway</h3>
        </div>
        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Transport</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {poolHealth ? 'HTTP Pool' : 'Checking...'}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Active Slots</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {poolHealth ? `${poolHealth.active_slots} / ${effective.pool_max_instances}` : '—'}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">ML Runtime</span>
              <p className="text-xs font-semibold mt-0.5">
                {poolHealth?.ml_ready ? (
                  <span className="text-green-700">Ready</span>
                ) : (
                  <span className="text-amber-600">Loading...</span>
                )}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Idle Timeout</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {Math.floor(effective.pool_idle_timeout_s / 60)}m
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Vector Storage */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-emerald-600 text-lg">database</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Vector Storage</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {VECTOR_BACKENDS.map((opt) => {
            const isSelected = effective.vector_backend === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => onUpdate({ vector_backend: opt.value as MemoryVectorBackend })}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'bg-emerald-50 border-2 border-emerald-500 shadow-sm'
                    : 'bg-white border border-slate-200 hover:border-emerald-300 cursor-pointer'
                }`}
              >
                <span className={`material-symbols-outlined text-xl ${isSelected ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {opt.icon}
                </span>
                <div className="flex-1">
                  <span className={`text-xs font-bold ${isSelected ? 'text-emerald-700' : 'text-slate-700'}`}>
                    {opt.label}
                  </span>
                  <p className="text-[9px] text-slate-400">{opt.description}</p>
                </div>
                {isSelected && <span className="material-symbols-outlined text-emerald-600 text-sm">check_circle</span>}
              </button>
            );
          })}
        </div>
      </section>

      {/* Section 3: Search Tuning */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-violet-600 text-lg">tune</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Search Tuning</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
              Similarity Weight
            </label>
            <input
              type="range"
              min={0.1} max={1.0} step={0.05}
              value={effective.similarity_weight}
              onChange={(e) => onUpdate({ similarity_weight: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-[9px] text-slate-400 mt-1">
              <span>Time-decay</span>
              <span className="font-mono">{effective.similarity_weight.toFixed(2)}</span>
              <span>Similarity</span>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
              Decay Half-Life
            </label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.decay_half_life_days}
                onChange={(e) => onUpdate({ decay_half_life_days: Math.max(1, parseFloat(e.target.value) || 30) })}
                min={1} max={365}
                className="w-full px-2 py-1.5 rounded text-xs font-mono"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">days</span>
            </div>
            <p className="text-[9px] text-slate-400 mt-1">Older notes rank lower in search</p>
          </div>
        </div>
      </section>

      {/* Section 4: Evolution */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-amber-600 text-lg">psychology</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Evolution</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Context Aware</label>
              <button
                onClick={() => onUpdate({ context_aware: !effective.context_aware })}
                className={`relative w-9 h-5 rounded-full transition-colors ${effective.context_aware ? 'bg-blue-500' : 'bg-slate-300'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${effective.context_aware ? 'translate-x-4' : ''}`} />
              </button>
            </div>
            <p className="text-[9px] text-slate-400">Include similar memories in LLM analysis</p>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Context Tree</label>
              <button
                onClick={() => onUpdate({ context_aware_tree: !effective.context_aware_tree })}
                className={`relative w-9 h-5 rounded-full transition-colors ${effective.context_aware_tree ? 'bg-blue-500' : 'bg-slate-300'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${effective.context_aware_tree ? 'translate-x-4' : ''}`} />
              </button>
            </div>
            <p className="text-[9px] text-slate-400">Include directory tree in analysis</p>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Max Links</label>
            <input
              type="number"
              value={effective.max_links}
              onChange={(e) => onUpdate({ max_links: Math.max(0, parseInt(e.target.value, 10) || 3) })}
              min={0} max={20}
              className="w-full px-2 py-1.5 rounded text-xs font-mono"
              style={inputStyle}
            />
            <p className="text-[9px] text-slate-400 mt-1">Links per note during evolution</p>
          </div>
        </div>
      </section>

      {/* Section 5: Sync */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-cyan-600 text-lg">sync</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Sync</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Auto Sync</label>
              <button
                onClick={() => onUpdate({ auto_sync: !effective.auto_sync })}
                className={`relative w-9 h-5 rounded-full transition-colors ${effective.auto_sync ? 'bg-blue-500' : 'bg-slate-300'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${effective.auto_sync ? 'translate-x-4' : ''}`} />
              </button>
            </div>
            <p className="text-[9px] text-slate-400">Periodic disk sync</p>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Sync Interval</label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.sync_interval_s}
                onChange={(e) => onUpdate({ sync_interval_s: Math.max(10, parseInt(e.target.value, 10) || 60) })}
                min={10} max={3600}
                disabled={!effective.auto_sync}
                className="w-full px-2 py-1.5 rounded text-xs font-mono disabled:opacity-40"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">sec</span>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Conflict Resolution</label>
            <select
              value={effective.conflict_resolution}
              onChange={(e) => onUpdate({ conflict_resolution: e.target.value })}
              className="w-full px-2 py-1.5 rounded text-xs"
              style={inputStyle}
            >
              <option value="last_modified">Last Modified Wins</option>
              <option value="disk">Disk Wins</option>
              <option value="memory">Memory Wins</option>
            </select>
          </div>
        </div>
      </section>

      {/* Section 6: Pool */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-orange-600 text-lg">memory</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Pool (HTTP Transport)</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Idle Timeout</label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.pool_idle_timeout_s}
                onChange={(e) => onUpdate({ pool_idle_timeout_s: Math.max(0, parseInt(e.target.value, 10) || 300) })}
                min={0} max={86400}
                className="w-full px-2 py-1.5 rounded text-xs font-mono"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">sec</span>
            </div>
            <p className="text-[9px] text-slate-400 mt-1">0 = never kill</p>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Max Instances</label>
            <input
              type="number"
              value={effective.pool_max_instances}
              onChange={(e) => onUpdate({ pool_max_instances: Math.max(1, parseInt(e.target.value, 10) || 10) })}
              min={1} max={100}
              className="w-full px-2 py-1.5 rounded text-xs font-mono"
              style={inputStyle}
            />
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Eviction Policy</label>
            <select
              value={effective.pool_eviction_policy}
              onChange={(e) => onUpdate({ pool_eviction_policy: e.target.value })}
              className="w-full px-2 py-1.5 rounded text-xs"
              style={inputStyle}
            >
              <option value="lru">LRU (Least Recently Used)</option>
              <option value="oldest">Oldest Created</option>
              <option value="none">None (reject when full)</option>
            </select>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">Slot Sync</label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.pool_sync_interval_s}
                onChange={(e) => onUpdate({ pool_sync_interval_s: Math.max(10, parseInt(e.target.value, 10) || 60) })}
                min={10} max={3600}
                className="w-full px-2 py-1.5 rounded text-xs font-mono"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">sec</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
