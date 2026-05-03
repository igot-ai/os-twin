'use client';

import { useEffect, useState } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import { ProviderIcon } from './ProviderIcon';
import type {
  MemorySettings,
  MemoryLLMBackend,
  MemoryEmbeddingBackend,
  MemoryVectorBackend,
} from '@/types/settings';
import { apiGet } from '@/lib/api-client';

export interface MemoryPanelProps {
  memory: MemorySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<MemorySettings>) => void;
}

// ── Backend option definitions ──────────────────────────────────────────────

interface BackendOption {
  value: string;
  label: string;
  description: string;
  requiresKey?: string; // env key name that must be set
  icon: string;
}

const LLM_BACKENDS: BackendOption[] = [
  { value: 'huggingface', label: 'HuggingFace (Local)', description: 'Local inference — no API key needed', icon: 'precision_manufacturing' },
  { value: 'gemini',      label: 'Gemini',              description: 'Google Gemini API', requiresKey: 'GOOGLE_API_KEY', icon: 'auto_awesome' },
  { value: 'openai',      label: 'OpenAI',              description: 'GPT models via OpenAI API', requiresKey: 'OPENAI_API_KEY', icon: 'smart_toy' },
  { value: 'ollama',      label: 'Ollama (Local)',       description: 'Local Ollama server', icon: 'dns' },
  { value: 'openrouter',  label: 'OpenRouter',           description: 'Multi-provider gateway', requiresKey: 'OPENROUTER_API_KEY', icon: 'hub' },
  { value: 'sglang',      label: 'SGLang (Local)',       description: 'Local SGLang server', icon: 'terminal' },
];

const EMBEDDING_BACKENDS: BackendOption[] = [
  { value: 'sentence-transformer', label: 'SentenceTransformer (Local)', description: 'Local embedding — no API key', icon: 'precision_manufacturing' },
  { value: 'gemini',               label: 'Gemini Embedding',           description: 'Google Gemini embedding API', requiresKey: 'GOOGLE_API_KEY', icon: 'auto_awesome' },
  { value: 'ollama',               label: 'Ollama (Local)',             description: 'Local Ollama embedding server', icon: 'dns' },
  { value: 'vertex',               label: 'Vertex AI',                  description: 'Google Vertex AI embedding API', requiresKey: 'GOOGLE_API_KEY', icon: 'cloud' },
];

const VECTOR_BACKENDS: BackendOption[] = [
  { value: 'zvec', label: 'zvec', description: 'Lightweight HNSW vector store — recommended', icon: 'database' },
  { value: 'chroma', label: 'ChromaDB', description: 'Feature-rich vector database', icon: 'view_in_ar' },
];

// ── Recommended models per backend ──────────────────────────────────────────

const LLM_MODEL_SUGGESTIONS: Record<string, { model: string; label: string }[]> = {
  huggingface: [
    { model: 'LiquidAI/LFM2-1.2B-Extract', label: 'LFM2 1.2B Extract (recommended)' },
  ],
  gemini: [
    { model: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview (recommended)' },
    { model: 'gemini-2.5-flash-preview-05-20', label: 'Gemini 2.5 Flash' },
    { model: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
  ],
  openai: [
    { model: 'gpt-4o-mini', label: 'GPT-4o Mini (recommended)' },
    { model: 'gpt-4o', label: 'GPT-4o' },
  ],
  ollama: [
    { model: 'llama3.2', label: 'Llama 3.2 (recommended)' },
    { model: 'mistral', label: 'Mistral' },
  ],
  openrouter: [
    { model: 'openai/gpt-4o-mini', label: 'GPT-4o Mini via OpenRouter' },
    { model: 'google/gemini-flash-1.5', label: 'Gemini Flash via OpenRouter' },
  ],
  sglang: [
    { model: 'default', label: 'Default model on SGLang server' },
  ],
};

const EMBEDDING_MODEL_SUGGESTIONS: Record<string, { model: string; label: string }[]> = {
  'sentence-transformer': [
    { model: 'microsoft/harrier-oss-v1-0.6b', label: 'Harrier OSS 0.6B (recommended)' },
    { model: 'all-MiniLM-L6-v2', label: 'MiniLM L6 v2 (lightweight)' },
  ],
  gemini: [
    { model: 'gemini-embedding-001', label: 'Gemini Embedding 001 (recommended)' },
  ],
  ollama: [
    { model: 'leoipulsar/harrier-0.6b', label: 'Harrier 0.6B (recommended)' },
    { model: 'embeddinggemma', label: 'Embedding Gemma' },
    { model: 'qwen3-embedding:0.6b', label: 'Qwen3 Embedding 0.6B' },
  ],
  vertex: [
    { model: 'gemini-embedding-001', label: 'Gemini Embedding 001 (recommended)' },
    { model: 'text-embedding-005', label: 'Text Embedding 005' },
  ],
};

// ── Defaults ────────────────────────────────────────────────────────────────

const DEFAULTS: Required<Pick<MemorySettings,
  'llm_backend' | 'llm_model' | 'embedding_backend' | 'embedding_model' |
  'vector_backend' | 'context_aware' | 'auto_sync' | 'auto_sync_interval' | 'ttl_days'
>> = {
  llm_backend: 'huggingface',
  llm_model: 'LiquidAI/LFM2-1.2B-Extract',
  embedding_backend: 'sentence-transformer',
  embedding_model: 'microsoft/harrier-oss-v1-0.6b',
  vector_backend: 'zvec',
  context_aware: true,
  auto_sync: true,
  auto_sync_interval: 60,
  ttl_days: 30,
};

// ── Component ───────────────────────────────────────────────────────────────

export function MemoryPanel({ memory, provenance = {}, onUpdate }: MemoryPanelProps) {
  const [availableProviders, setAvailableProviders] = useState<Set<string>>(new Set());

  // Detect which API keys are available (for showing provider availability badges)
  useEffect(() => {
    const detect = async () => {
      try {
        const raw = await apiGet<Record<string, { is_set: boolean }>>('/settings/vault/providers');
        const entries = (raw as { keys?: Record<string, { is_set: boolean }> }).keys ?? raw;
        const providers = new Set<string>();
        Object.entries(entries).forEach(([key, value]) => {
          if (value?.is_set) providers.add(key);
        });
        setAvailableProviders(providers);
      } catch {
        setAvailableProviders(new Set());
      }
    };
    detect();
  }, []);

  // Resolve a provider key to whether it's available
  const isKeyAvailable = (envKey?: string): boolean | null => {
    if (!envKey) return null; // no key needed
    const keyMap: Record<string, string> = {
      GOOGLE_API_KEY: 'google',
      OPENAI_API_KEY: 'openai',
      OPENROUTER_API_KEY: 'openrouter',
    };
    const provider = keyMap[envKey];
    return provider ? availableProviders.has(provider) : false;
  };

  // Merge with defaults
  const effective = { ...DEFAULTS, ...memory };

  // When LLM backend changes, auto-set the recommended model
  const handleLLMBackendChange = (backend: MemoryLLMBackend) => {
    const suggestions = LLM_MODEL_SUGGESTIONS[backend];
    const recommendedModel = suggestions?.[0]?.model ?? '';
    onUpdate({ llm_backend: backend, llm_model: recommendedModel });
  };

  // When embedding backend changes, auto-set the recommended model
  const handleEmbeddingBackendChange = (backend: MemoryEmbeddingBackend) => {
    const suggestions = EMBEDDING_MODEL_SUGGESTIONS[backend];
    const recommendedModel = suggestions?.[0]?.model ?? '';
    onUpdate({ embedding_backend: backend, embedding_model: recommendedModel });
  };

  // Input field style constants
  const inputStyle = {
    background: '#f1f5f9',
    border: '1px solid #e2e8f0',
    color: '#0f172a',
  };

  return (
    <div className="space-y-8">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-primary bg-primary-container px-2 py-0.5 rounded">
            MEMORY_PLATFORM
          </span>
          <span className="text-xs text-on-surface-variant">/ configuration / agentic-memory</span>
        </div>
        <p className="text-sm text-on-surface-variant">
          Configure the agentic memory system: processing model, embeddings, and vector storage.
          Settings map to <code className="font-mono text-[10px] bg-slate-100 px-1 py-0.5 rounded">MEMORY_*</code> environment variables.
        </p>
      </div>

      {/* ── Section 1: Processing Model ────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">psychology</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Processing Model</h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">MEMORY_LLM_BACKEND / MEMORY_LLM_MODEL</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* LLM Backend Selector */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              LLM Backend
            </label>
            <div className="space-y-1.5">
              {LLM_BACKENDS.map((opt) => {
                const isSelected = effective.llm_backend === opt.value;
                const keyAvailable = isKeyAvailable(opt.requiresKey);
                const isDisabled = keyAvailable === false;
                return (
                  <button
                    key={opt.value}
                    onClick={() => !isDisabled && handleLLMBackendChange(opt.value as MemoryLLMBackend)}
                    disabled={isDisabled}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isSelected
                        ? 'bg-blue-50 border-2 border-blue-500 shadow-sm'
                        : isDisabled
                        ? 'bg-slate-50 border border-slate-100 opacity-50 cursor-not-allowed'
                        : 'bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50/30 cursor-pointer'
                    }`}
                  >
                    <ProviderIcon provider={opt.value} size={16} className={isSelected ? '' : 'opacity-50'} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-xs font-semibold ${isSelected ? 'text-blue-700' : 'text-slate-700'}`}>
                          {opt.label}
                        </span>
                        {keyAvailable === true && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                            Key Set
                          </span>
                        )}
                        {keyAvailable === false && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                            No Key
                          </span>
                        )}
                        {keyAvailable === null && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            Local
                          </span>
                        )}
                      </div>
                      <p className="text-[9px] text-slate-400 truncate">{opt.description}</p>
                    </div>
                    {isSelected && (
                      <span className="material-symbols-outlined text-blue-600 text-sm">check_circle</span>
                    )}
                  </button>
                );
              })}
            </div>
            {provenance.llm_backend && <ProvenanceChip source={provenance.llm_backend} />}
          </div>

          {/* LLM Model Selector */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              Model
            </label>
            {/* Suggested models for the selected backend */}
            {(LLM_MODEL_SUGGESTIONS[effective.llm_backend] ?? []).length > 0 && (
              <div className="space-y-1 mb-3">
                {(LLM_MODEL_SUGGESTIONS[effective.llm_backend] ?? []).map((s) => {
                  const isActive = effective.llm_model === s.model;
                  return (
                    <button
                      key={s.model}
                      onClick={() => onUpdate({ llm_model: s.model })}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all flex items-center justify-between ${
                        isActive
                          ? 'bg-blue-50 border border-blue-400 text-blue-700 font-semibold'
                          : 'bg-white border border-slate-200 text-slate-600 hover:border-blue-300'
                      }`}
                    >
                      <span className="font-mono text-[10px]">{s.label}</span>
                      {isActive && <span className="material-symbols-outlined text-blue-500 text-sm">check</span>}
                    </button>
                  );
                })}
              </div>
            )}
            {/* Custom model input */}
            <div>
              <label className="text-[9px] text-slate-400 mb-1 block">Or enter a custom model ID:</label>
              <input
                type="text"
                value={effective.llm_model}
                onChange={(e) => onUpdate({ llm_model: e.target.value })}
                placeholder="e.g. LiquidAI/LFM2-1.2B-Extract"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={inputStyle}
              />
            </div>
            {provenance.llm_model && <ProvenanceChip source={provenance.llm_model} />}
          </div>
        </div>
      </section>

      {/* ── Section 2: Embedding ───────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-purple-600 text-lg">layers</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Embedding</h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">MEMORY_EMBEDDING_BACKEND / MEMORY_EMBEDDING_MODEL</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Embedding Backend */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              Embedding Backend
            </label>
            <div className="space-y-1.5">
              {EMBEDDING_BACKENDS.map((opt) => {
                const isSelected = effective.embedding_backend === opt.value;
                const keyAvailable = isKeyAvailable(opt.requiresKey);
                const isDisabled = keyAvailable === false;
                return (
                  <button
                    key={opt.value}
                    onClick={() => !isDisabled && handleEmbeddingBackendChange(opt.value as MemoryEmbeddingBackend)}
                    disabled={isDisabled}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isSelected
                        ? 'bg-purple-50 border-2 border-purple-500 shadow-sm'
                        : isDisabled
                        ? 'bg-slate-50 border border-slate-100 opacity-50 cursor-not-allowed'
                        : 'bg-white border border-slate-200 hover:border-purple-300 hover:bg-purple-50/30 cursor-pointer'
                    }`}
                  >
                    <ProviderIcon provider={opt.value} size={16} className={isSelected ? '' : 'opacity-50'} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-xs font-semibold ${isSelected ? 'text-purple-700' : 'text-slate-700'}`}>
                          {opt.label}
                        </span>
                        {keyAvailable === true && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-green-100 text-green-700">Key Set</span>
                        )}
                        {keyAvailable === false && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">No Key</span>
                        )}
                        {keyAvailable === null && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">Local</span>
                        )}
                      </div>
                      <p className="text-[9px] text-slate-400 truncate">{opt.description}</p>
                    </div>
                    {isSelected && (
                      <span className="material-symbols-outlined text-purple-600 text-sm">check_circle</span>
                    )}
                  </button>
                );
              })}
            </div>
            {provenance.embedding_backend && <ProvenanceChip source={provenance.embedding_backend} />}
          </div>

          {/* Embedding Model */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              Embedding Model
            </label>
            {(EMBEDDING_MODEL_SUGGESTIONS[effective.embedding_backend] ?? []).length > 0 && (
              <div className="space-y-1 mb-3">
                {(EMBEDDING_MODEL_SUGGESTIONS[effective.embedding_backend] ?? []).map((s) => {
                  const isActive = effective.embedding_model === s.model;
                  return (
                    <button
                      key={s.model}
                      onClick={() => onUpdate({ embedding_model: s.model })}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all flex items-center justify-between ${
                        isActive
                          ? 'bg-purple-50 border border-purple-400 text-purple-700 font-semibold'
                          : 'bg-white border border-slate-200 text-slate-600 hover:border-purple-300'
                      }`}
                    >
                      <span className="font-mono text-[10px]">{s.label}</span>
                      {isActive && <span className="material-symbols-outlined text-purple-500 text-sm">check</span>}
                    </button>
                  );
                })}
              </div>
            )}
            <div>
              <label className="text-[9px] text-slate-400 mb-1 block">Or enter a custom model ID:</label>
              <input
                type="text"
                value={effective.embedding_model}
                onChange={(e) => onUpdate({ embedding_model: e.target.value })}
                placeholder="e.g. microsoft/harrier-oss-v1-0.6b"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={inputStyle}
              />
            </div>
            {provenance.embedding_model && <ProvenanceChip source={provenance.embedding_model} />}
          </div>
        </div>
      </section>

      {/* ── Section 3: Vector Storage ──────────────────────── */}
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

      {/* ── Section 4: Behaviour ───────────────────────────── */}
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

      {/* ── Env Mapping Reference ──────────────────────────── */}
      <section className="border-t border-slate-200 pt-4">
        <details className="group">
          <summary className="flex items-center gap-2 cursor-pointer text-xs text-slate-400 hover:text-slate-600">
            <span className="material-symbols-outlined text-sm">info</span>
            <span className="font-mono text-[10px]">Environment variable mapping</span>
            <span className="material-symbols-outlined text-sm group-open:rotate-180 transition-transform">expand_more</span>
          </summary>
          <div className="mt-3 bg-slate-50 rounded-lg p-3 font-mono text-[10px] text-slate-600 space-y-1">
            <div className="grid grid-cols-[1fr_auto_1fr] gap-x-3 gap-y-0.5">
              <span className="text-slate-400">MEMORY_LLM_BACKEND</span>
              <span className="text-slate-300">=</span>
              <span>{effective.llm_backend}</span>

              <span className="text-slate-400">MEMORY_LLM_MODEL</span>
              <span className="text-slate-300">=</span>
              <span>{effective.llm_model}</span>

              <span className="text-slate-400">MEMORY_EMBEDDING_BACKEND</span>
              <span className="text-slate-300">=</span>
              <span>{effective.embedding_backend}</span>

              <span className="text-slate-400">MEMORY_EMBEDDING_MODEL</span>
              <span className="text-slate-300">=</span>
              <span>{effective.embedding_model}</span>

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
          </div>
        </details>
      </section>
    </div>
  );
}
