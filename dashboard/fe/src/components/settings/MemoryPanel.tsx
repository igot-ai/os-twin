'use client';

import { useEffect, useState } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import type {
  MemorySettings,
  MemoryVectorBackend,
} from '@/types/settings';
import { apiGet } from '@/lib/api-client';

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
  auto_sync: true,
  auto_sync_interval: 60,
  ttl_days: 30,
};

interface GatewayInfo {
  provider: string;
  completion_model: string;
  memory_model: string;
  cloud_embedding_model: string;
  timeout: number;
}

export function MemoryPanel({ memory, provenance = {}, onUpdate }: MemoryPanelProps) {
  const [gateway, setGateway] = useState<GatewayInfo | null>(null);
  const [poolHealth, setPoolHealth] = useState<any>(null);

  // Fetch gateway config and pool health
  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const [aiStats, health] = await Promise.allSettled([
          fetch('/api/ai/stats').then(r => r.ok ? r.json() : null),
          fetch('/api/memory-pool/health').then(r => r.ok ? r.json() : null),
        ]);
        if (aiStats.status === 'fulfilled' && aiStats.value) {
          setGateway(aiStats.value);
        }
        if (health.status === 'fulfilled' && health.value) {
          setPoolHealth(health.value);
        }
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
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-primary bg-primary-container px-2 py-0.5 rounded">
            MEMORY_PLATFORM
          </span>
          <span className="text-xs text-on-surface-variant">/ configuration / agentic-memory</span>
        </div>
        <p className="text-sm text-on-surface-variant">
          Memory system configuration. LLM and embedding calls are routed through the
          centralized AI gateway — configure models in <strong>Provider Config</strong> and
          monitor calls in <strong>AI Monitor</strong>.
        </p>
      </div>

      {/* Section 1: AI Gateway Status */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">hub</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">AI Gateway</h3>
          <span className="text-[9px] text-slate-400 ml-auto">All LLM + embedding calls centralized</span>
        </div>

        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 space-y-3">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-blue-600 text-xl mt-0.5">check_circle</span>
            <div className="flex-1">
              <p className="text-xs font-semibold text-blue-800">
                All memory AI calls go through <code className="bg-blue-100 px-1 rounded text-[10px]">dashboard/ai/</code>
              </p>
              <p className="text-[10px] text-blue-600 mt-1">
                LLM completions use <code className="bg-blue-100 px-1 rounded">get_completion(purpose=&quot;memory&quot;)</code>.
                Embeddings use <code className="bg-blue-100 px-1 rounded">get_embedding()</code>.
                Every call is logged in the AI Monitor.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Transport</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {poolHealth ? 'HTTP Pool' : 'Checking...'}
              </p>
              <p className="text-[9px] text-slate-400">/api/memory-pool/mcp</p>
            </div>
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Active Slots</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {poolHealth ? `${poolHealth.active_slots} / ${poolHealth.config?.max_instances ?? '?'}` : '—'}
              </p>
              <p className="text-[9px] text-slate-400">memory instances</p>
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
              <p className="text-[9px] text-slate-400">embedding models</p>
            </div>
            <div className="bg-white rounded-lg border border-blue-100 p-2.5">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Idle Timeout</span>
              <p className="text-xs font-semibold text-slate-800 mt-0.5">
                {poolHealth?.config?.idle_timeout_s ? `${Math.floor(poolHealth.config.idle_timeout_s / 60)}m` : '—'}
              </p>
              <p className="text-[9px] text-slate-400">before slot cleanup</p>
            </div>
          </div>
        </div>
      </section>

      {/* Section 2: Vector Storage */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-emerald-600 text-lg">database</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Vector Storage</h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">MEMORY_VECTOR_BACKEND</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {VECTOR_BACKENDS.map((opt) => {
            const isSelected = effective.vector_backend === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => onUpdate({ vector_backend: opt.value as MemoryVectorBackend, vector_store: opt.value })}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'bg-emerald-50 border-2 border-emerald-500 shadow-sm'
                    : 'bg-white border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 cursor-pointer'
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
                {isSelected && (
                  <span className="material-symbols-outlined text-emerald-600 text-sm">check_circle</span>
                )}
              </button>
            );
          })}
        </div>
        {provenance.vector_backend && <ProvenanceChip source={provenance.vector_backend} />}
      </section>

      {/* Section 3: Behaviour */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-amber-600 text-lg">tune</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Behaviour</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Context-aware toggle */}
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Context Aware
              </label>
              <button
                onClick={() => onUpdate({ context_aware: !effective.context_aware })}
                className={`relative w-9 h-5 rounded-full transition-colors ${
                  effective.context_aware ? 'bg-blue-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    effective.context_aware ? 'translate-x-4' : ''
                  }`}
                />
              </button>
            </div>
            <p className="text-[9px] text-slate-400">Include similar memories in LLM analysis context</p>
            {provenance.context_aware && <ProvenanceChip source={provenance.context_aware} />}
          </div>

          {/* Auto-sync toggle */}
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Auto Sync
              </label>
              <button
                onClick={() => onUpdate({ auto_sync: !effective.auto_sync })}
                className={`relative w-9 h-5 rounded-full transition-colors ${
                  effective.auto_sync ? 'bg-blue-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    effective.auto_sync ? 'translate-x-4' : ''
                  }`}
                />
              </button>
            </div>
            <p className="text-[9px] text-slate-400">Periodic disk sync of memory data</p>
            {provenance.auto_sync && <ProvenanceChip source={provenance.auto_sync} />}
          </div>

          {/* Sync interval */}
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
              Sync Interval
            </label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.auto_sync_interval}
                onChange={(e) => onUpdate({ auto_sync_interval: Math.max(10, parseInt(e.target.value, 10) || 60) })}
                min={10}
                max={3600}
                disabled={!effective.auto_sync}
                className="w-full px-2 py-1.5 rounded text-xs font-mono disabled:opacity-40"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">sec</span>
            </div>
            {provenance.auto_sync_interval && <ProvenanceChip source={provenance.auto_sync_interval} />}
          </div>

          {/* TTL */}
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1.5 block text-slate-500">
              TTL
            </label>
            <div className="flex items-baseline gap-1">
              <input
                type="number"
                value={effective.ttl_days}
                onChange={(e) => onUpdate({ ttl_days: Math.max(1, parseInt(e.target.value, 10) || 30) })}
                min={1}
                max={365}
                className="w-full px-2 py-1.5 rounded text-xs font-mono"
                style={inputStyle}
              />
              <span className="text-[9px] text-slate-400 whitespace-nowrap">days</span>
            </div>
            <p className="text-[9px] text-slate-400 mt-1">Auto-delete old entries</p>
            {provenance.ttl_days && <ProvenanceChip source={provenance.ttl_days} />}
          </div>
        </div>
      </section>

      {/* Env Mapping Reference */}
      <section className="border-t border-slate-200 pt-4">
        <details className="group">
          <summary className="flex items-center gap-2 cursor-pointer text-xs text-slate-400 hover:text-slate-600">
            <span className="material-symbols-outlined text-sm">info</span>
            <span className="font-mono text-[10px]">Environment variable mapping</span>
            <span className="material-symbols-outlined text-sm group-open:rotate-180 transition-transform">expand_more</span>
          </summary>
          <div className="mt-3 bg-slate-50 rounded-lg p-3 font-mono text-[10px] text-slate-600 space-y-1">
            <div className="grid grid-cols-[1fr_auto_1fr] gap-x-3 gap-y-0.5">
              <span className="text-slate-400">MEMORY_VECTOR_BACKEND</span>
              <span className="text-slate-300">=</span>
              <span>{effective.vector_backend}</span>

              <span className="text-slate-400">MEMORY_CONTEXT_AWARE</span>
              <span className="text-slate-300">=</span>
              <span>{effective.context_aware ? 'true' : 'false'}</span>

              <span className="text-slate-400">MEMORY_AUTO_SYNC</span>
              <span className="text-slate-300">=</span>
              <span>{effective.auto_sync ? 'true' : 'false'}</span>

              <span className="text-slate-400">MEMORY_AUTO_SYNC_INTERVAL</span>
              <span className="text-slate-300">=</span>
              <span>{effective.auto_sync_interval}</span>
            </div>
            <p className="text-[9px] text-slate-400 mt-2 pt-2 border-t border-slate-200">
              LLM and embedding model settings are configured via <strong>Provider Config</strong> and the AI gateway.
              The <code>MEMORY_LLM_*</code> and <code>MEMORY_EMBEDDING_*</code> env vars are no longer used.
            </p>
          </div>
        </details>
      </section>
    </div>
  );
}
