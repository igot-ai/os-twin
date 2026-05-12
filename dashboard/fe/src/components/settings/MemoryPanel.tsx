'use client';

import { useEffect, useMemo, useState } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import { ProviderIcon } from './ProviderIcon';
import { ModelSelect } from './ModelSelect';
import { ModelConfigSample } from './ModelConfigSample';
import type {
  MemorySettings,
  MemoryLLMBackend,
  MemoryEmbeddingBackend,
  MemoryVectorBackend,
  ModelInfo,
} from '@/types/settings';
import { apiGet } from '@/lib/api-client';

export interface MemoryPanelProps {
  memory: MemorySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<MemorySettings>) => void;
  allModels?: ModelInfo[];
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
  { value: 'ollama',           label: 'Ollama (Local)',        description: 'Local Ollama server', icon: 'dns' },
  { value: 'openai-compatible', label: 'OpenAI-Compatible',    description: 'Any OpenAI-compatible API server', icon: 'api' },
];

const EMBEDDING_BACKENDS: BackendOption[] = [
  { value: 'ollama',               label: 'Ollama (Local)',             description: 'Local Ollama embedding server', icon: 'dns' },
  { value: 'openai-compatible',    label: 'OpenAI-Compatible',          description: 'Any OpenAI-compatible embedding API', icon: 'api' },
];

const VECTOR_BACKENDS: BackendOption[] = [
  { value: 'zvec', label: 'zvec', description: 'Lightweight HNSW vector store — recommended', icon: 'database' },
  { value: 'chroma', label: 'ChromaDB', description: 'Feature-rich vector database', icon: 'view_in_ar' },
];

// ── Recommended models per backend ──────────────────────────────────────────

const LLM_MODEL_SUGGESTIONS: Record<string, { model: string; label: string }[]> = {
  ollama: [
    { model: 'llama3.2', label: 'Llama 3.2 (recommended)' },
    { model: 'mistral', label: 'Mistral' },
  ],
  'openai-compatible': [
    { model: 'gpt-4', label: 'GPT-4' },
    { model: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  ],
};

const EMBEDDING_MODEL_SUGGESTIONS: Record<string, { model: string; label: string }[]> = {
  ollama: [
    { model: 'leoipulsar/harrier-0.6b', label: 'Harrier 0.6B (recommended)' },
    { model: 'embeddinggemma', label: 'Embedding Gemma' },
    { model: 'qwen3-embedding:0.6b', label: 'Qwen3 Embedding 0.6B' },
  ],
  'openai-compatible': [
    { model: 'default', label: 'Model configured on your server' },
  ],
};

// ── Defaults ────────────────────────────────────────────────────────────────

const DEFAULTS: Required<Pick<MemorySettings,
  'llm_backend' | 'llm_model' | 'embedding_backend' | 'embedding_model' |
  'vector_backend' | 'context_aware' | 'auto_sync' | 'auto_sync_interval' | 'ttl_days'
>> = {
  llm_backend: '',
  llm_model: '',
  embedding_backend: '',
  embedding_model: '',
  vector_backend: 'zvec',
  context_aware: true,
  auto_sync: true,
  auto_sync_interval: 60,
  ttl_days: 30,
};

// ── Component ───────────────────────────────────────────────────────────────

export function MemoryPanel({ memory, provenance = {}, onUpdate, allModels = [] }: MemoryPanelProps) {
  const [availableProviders, setAvailableProviders] = useState<Set<string>>(new Set());

  // Merge with defaults
  const effective = { ...DEFAULTS, ...memory };

  // Local state for all inputs - initialized from effective settings
  const [draft, setDraft] = useState<MemorySettings>(effective);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [llmModelInput, setLlmModelInput] = useState(draft.llm_model ?? '');
  const [embeddingModelInput, setEmbeddingModelInput] = useState(draft.embedding_model ?? '');
  const [syncIntervalInput, setSyncIntervalInput] = useState(String(draft.auto_sync_interval ?? 60));
  const [ttlDaysInput, setTtlDaysInput] = useState(String(draft.ttl_days ?? 30));

  // OpenAI-compatible specific fields
  const [llmCompatibleUrl, setLlmCompatibleUrl] = useState<string>((draft.llm_compatible_url as string) ?? '');
  const [llmCompatibleKey, setLlmCompatibleKey] = useState<string>((draft.llm_compatible_key as string) ?? '');
  const [embeddingCompatibleUrl, setEmbeddingCompatibleUrl] = useState<string>((draft.embedding_compatible_url as string) ?? '');
  const [embeddingCompatibleKey, setEmbeddingCompatibleKey] = useState<string>((draft.embedding_compatible_key as string) ?? '');

  // Sync draft if external memory settings change (but don't overwrite if user is editing)
  useEffect(() => {
    if (!hasChanges) {
      setDraft({ ...DEFAULTS, ...memory });
      setLlmModelInput(memory.llm_model ?? '');
      setEmbeddingModelInput(memory.embedding_model ?? '');
      setSyncIntervalInput(String(memory.auto_sync_interval ?? 60));
      setTtlDaysInput(String(memory.ttl_days ?? 30));
      setLlmCompatibleUrl((memory.llm_compatible_url as string) ?? '');
      setLlmCompatibleKey((memory.llm_compatible_key as string) ?? '');
      setEmbeddingCompatibleUrl((memory.embedding_compatible_url as string) ?? '');
      setEmbeddingCompatibleKey((memory.embedding_compatible_key as string) ?? '');
    }
  }, [memory, hasChanges]);

  // Helper to update draft
  const updateDraft = (updates: Partial<MemorySettings>) => {
    setDraft((prev) => ({ ...prev, ...updates }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onUpdate(draft);
      setHasChanges(false);
    } finally {
      setIsSaving(false);
    }
  };

  const [ollamaHealth, setOllamaHealth] = useState<Record<string, { running: boolean; model_exists: boolean; pulling: boolean; progress?: string }>>({});
  const [ollamaModels, setOllamaModels] = useState<{ raw_name: string; display_name: string; is_embed: boolean }[]>([]);

  // Fetch all installed Ollama models
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const { apiGet } = await import('@/lib/api-client');
        const data = await apiGet<{ models: { raw_name: string; display_name: string; is_embed: boolean }[] }>('/settings/ollama/models');
        setOllamaModels(data.models || []);
      } catch (err) {
        setOllamaModels([]);
      }
    };

    if (draft.llm_backend === 'ollama' || draft.embedding_backend === 'ollama') {
      fetchModels();
    }
  }, [draft.llm_backend, draft.embedding_backend]);

  // Check health when model changes
  useEffect(() => {
    const checkHealth = async (model: string) => {
      if (!model) return;
      try {
        const { apiGet } = await import('@/lib/api-client');
        const data = await apiGet<{ running: boolean; model_exists: boolean }>(`/settings/ollama/health?model=${model}`);
        setOllamaHealth((prev) => ({
          ...prev,
          [model]: { ...prev[model], ...data, pulling: prev[model]?.pulling || false },
        }));
      } catch (err) {
        setOllamaHealth((prev) => ({
          ...prev,
          [model]: { running: false, model_exists: false, pulling: false, progress: 'Could not connect to backend to check Ollama status.' },
        }));
      }
    };

    if (draft.llm_backend === 'ollama' && draft.llm_model) {
      checkHealth(draft.llm_model);
    }
    if (draft.embedding_backend === 'ollama' && draft.embedding_model) {
      checkHealth(draft.embedding_model);
    }
  }, [draft.llm_backend, draft.llm_model, draft.embedding_backend, draft.embedding_model]);

  // Filter out embedding models from the model picker
  const chatModels = useMemo(
    () => allModels.filter((m) => !m.id.toLowerCase().includes('embed')),
    [allModels],
  );

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

  const pullModel = async (model: string) => {
    setOllamaHealth((prev) => ({
      ...prev,
      [model]: { ...prev[model], pulling: true, progress: 'Starting pull...' },
    }));

    try {
      const response = await fetch('/api/settings/ollama/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });

      if (!response.body) throw new Error('No body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split('\n').filter(Boolean);
        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            if (data.error) throw new Error(data.error);
            if (data.status) {
              let msg = data.status;
              if (data.total && data.completed) {
                const percent = Math.round((data.completed / data.total) * 100);
                msg += ` (${percent}%)`;
              }
              setOllamaHealth((prev) => ({
                ...prev,
                [model]: { ...prev[model], progress: msg },
              }));
            }
          } catch (e) {
            // parse error
          }
        }
      }

      // Success! Re-check health
      const { apiGet } = await import('@/lib/api-client');
      const data = await apiGet<{ running: boolean; model_exists: boolean }>(`/settings/ollama/health?model=${model}`);
      setOllamaHealth((prev) => ({
        ...prev,
        [model]: { ...data, pulling: false },
      }));

    } catch (e) {
      setOllamaHealth((prev) => ({
        ...prev,
        [model]: { ...prev[model], pulling: false, progress: `Error: ${e}` },
      }));
    }
  };

  const renderOllamaBanner = () => {
    const usesOllamaLlm = draft.llm_backend === 'ollama' && draft.llm_model;
    const usesOllamaEmbed = draft.embedding_backend === 'ollama' && draft.embedding_model;

    if (!usesOllamaLlm && !usesOllamaEmbed) return null;

    const llmStatus = usesOllamaLlm && draft.llm_model ? ollamaHealth[draft.llm_model] : null;
    const embedStatus = usesOllamaEmbed && draft.embedding_model ? ollamaHealth[draft.embedding_model] : null;

    if ((usesOllamaLlm && !llmStatus) || (usesOllamaEmbed && !embedStatus)) return null;

    const notRunning = (llmStatus && !llmStatus.running) || (embedStatus && !embedStatus.running);
    const pullingLlm = llmStatus?.pulling;
    const pullingEmbed = embedStatus?.pulling;
    const missingLlm = llmStatus?.running && !llmStatus.model_exists && !pullingLlm;
    const missingEmbed = embedStatus?.running && !embedStatus.model_exists && !pullingEmbed;

    if (notRunning) {
      return (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <span className="material-symbols-outlined text-red-600 mt-0.5">error</span>
          <div>
            <h4 className="text-sm font-bold text-red-800">Ollama is not running</h4>
            <p className="text-xs text-red-600 mt-1">You have selected Ollama as a backend, but the local Ollama server cannot be reached. Please start the Ollama application.</p>
          </div>
        </div>
      );
    }

    const pullingModels = [];
    if (pullingLlm) pullingModels.push({ model: draft.llm_model!, progress: llmStatus.progress });
    if (pullingEmbed && draft.embedding_model !== draft.llm_model) {
      pullingModels.push({ model: draft.embedding_model!, progress: embedStatus.progress });
    }

    if (pullingModels.length > 0) {
      return (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg flex flex-col gap-2">
          {pullingModels.map(pm => (
            <div key={pm.model} className="flex items-center gap-3">
              <span className="material-symbols-outlined text-blue-600 animate-spin">progress_activity</span>
              <div className="text-sm text-blue-800 font-medium">
                Downloading {pm.model}... <span className="text-xs font-normal text-blue-600 ml-2">{pm.progress}</span>
              </div>
            </div>
          ))}
        </div>
      );
    }

    const missingModels = [];
    if (missingLlm) missingModels.push(draft.llm_model!);
    if (missingEmbed && !missingModels.includes(draft.embedding_model!)) missingModels.push(draft.embedding_model!);

    if (missingModels.length > 0) {
      return (
        <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3">
          <span className="material-symbols-outlined text-amber-600 mt-0.5">warning</span>
          <div className="flex-1">
            <h4 className="text-sm font-bold text-amber-800">Missing Local Models</h4>
            <p className="text-xs text-amber-700 mt-1 mb-3">The following models are required but not found in your local Ollama installation.</p>
            <div className="flex flex-wrap gap-2">
              {missingModels.map(model => (
                <button
                  key={model}
                  onClick={() => pullModel(model)}
                  className="px-3 py-1.5 bg-amber-600 text-white text-xs font-semibold rounded hover:bg-amber-700 transition-colors shadow-sm"
                >
                  Download {model}
                </button>
              ))}
            </div>
          </div>
        </div>
      );
    }

    return null;
  };

  // When LLM backend changes, auto-set the recommended model
  const handleLLMBackendChange = (backend: MemoryLLMBackend) => {
    const suggestions = LLM_MODEL_SUGGESTIONS[backend];
    const recommendedModel = suggestions?.[0]?.model ?? '';
    updateDraft({ llm_backend: backend, llm_model: recommendedModel });
  };

  // When embedding backend changes, auto-set the recommended model
  const handleEmbeddingBackendChange = (backend: MemoryEmbeddingBackend) => {
    const suggestions = EMBEDDING_MODEL_SUGGESTIONS[backend];
    const recommendedModel = suggestions?.[0]?.model ?? '';
    updateDraft({ embedding_backend: backend, embedding_model: recommendedModel });
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

        {renderOllamaBanner()}
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
                const isSelected = draft.llm_backend === opt.value;
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
                        {!opt.requiresKey && opt.value !== '' && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            Local
                          </span>
                        )}
                        {opt.requiresKey === undefined && opt.value === 'openai-compatible' && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Custom</span>
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
            {(draft.llm_backend && (LLM_MODEL_SUGGESTIONS[draft.llm_backend] ?? []).length > 0) && (
              <div className="space-y-1 mb-3">
                {(draft.llm_backend ? (LLM_MODEL_SUGGESTIONS[draft.llm_backend] ?? []) : []).map((s: { model: string; label: string }) => {
                  const isActive = draft.llm_model === s.model;
                  return (
                    <button
                      key={s.model}
                      onClick={() => updateDraft({ llm_model: s.model })}
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
                value={llmModelInput}
                onChange={(e) => setLlmModelInput(e.target.value)}
                onBlur={() => updateDraft({ llm_model: llmModelInput })}
                placeholder="e.g. llama3.2"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={inputStyle}
              />
            </div>

            {/* Installed Ollama Models Dropdown */}
            {draft.llm_backend === 'ollama' && ollamaModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Or pick from installed Ollama models:
                </label>
                <select
                  value={draft.llm_model || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setLlmModelInput(val);
                    updateDraft({ llm_model: val });
                  }}
                  className="w-full px-3 py-2 rounded-md text-xs font-mono bg-white border border-slate-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                >
                  <option value="" disabled>— Select installed model —</option>
                  {ollamaModels.filter(m => !m.is_embed).map(m => (
                    <option key={m.raw_name} value={m.display_name}>{m.display_name}</option>
                  ))}
                </select>
              </div>
            )}

            {provenance.llm_model && <ProvenanceChip source={provenance.llm_model} />}

            {/* Model picker from configured providers */}
            {draft.llm_backend === 'openai-compatible' && chatModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Pick from configured providers:
                </label>
                <ModelSelect
                  value={draft.llm_model || ''}
                  onChange={(modelId) => {
                    setLlmModelInput(modelId);
                    updateDraft({ llm_model: modelId });
                  }}
                  models={chatModels}
                  showTier={true}
                  showContext={true}
                  placeholder="— Select from providers —"
                />
              </div>
            )}

            {/* OpenAI-compatible specific fields */}
            {draft.llm_backend === 'openai-compatible' && (
              <div className="mt-4 space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <label className="text-[9px] font-semibold text-slate-600 mb-1 block">API Endpoint URL</label>
                  <input
                    type="text"
                    value={llmCompatibleUrl}
                    onChange={(e) => setLlmCompatibleUrl(e.target.value)}
                    onBlur={() => updateDraft({ llm_compatible_url: llmCompatibleUrl })}
                    placeholder="http://localhost:8000/v1"
                    className="w-full px-3 py-2 rounded-md text-xs font-mono"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="text-[9px] font-semibold text-slate-600 mb-1 block">API Key (optional)</label>
                  <input
                    type="password"
                    value={llmCompatibleKey}
                    onChange={(e) => setLlmCompatibleKey(e.target.value)}
                    onBlur={() => updateDraft({ llm_compatible_key: llmCompatibleKey })}
                    placeholder="sk-..."
                    className="w-full px-3 py-2 rounded-md text-xs font-mono"
                    style={inputStyle}
                  />
                </div>
              </div>
            )}

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
                const isSelected = draft.embedding_backend === opt.value;
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
                        {!opt.requiresKey && opt.value !== '' && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            Local
                          </span>
                        )}
                        {opt.requiresKey === undefined && opt.value === 'openai-compatible' && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Custom</span>
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
            {(draft.embedding_backend && (EMBEDDING_MODEL_SUGGESTIONS[draft.embedding_backend] ?? []).length > 0) && (
              <div className="space-y-1 mb-3">
                {(draft.embedding_backend ? (EMBEDDING_MODEL_SUGGESTIONS[draft.embedding_backend] ?? []) : []).map((s: { model: string; label: string }) => {
                  const isActive = draft.embedding_model === s.model;
                  return (
                    <button
                      key={s.model}
                      onClick={() => updateDraft({ embedding_model: s.model })}
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
                value={embeddingModelInput}
                onChange={(e) => setEmbeddingModelInput(e.target.value)}
                onBlur={() => updateDraft({ embedding_model: embeddingModelInput })}
                placeholder="e.g. leoipulsar/harrier-0.6b"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={inputStyle}
              />
            </div>

            {/* Installed Ollama Models Dropdown */}
            {draft.embedding_backend === 'ollama' && ollamaModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Or pick from installed Ollama models:
                </label>
                <select
                  value={draft.embedding_model || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setEmbeddingModelInput(val);
                    updateDraft({ embedding_model: val });
                  }}
                  className="w-full px-3 py-2 rounded-md text-xs font-mono bg-white border border-slate-200 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none"
                >
                  <option value="" disabled>— Select installed model —</option>
                  {ollamaModels.filter(m => m.is_embed).map(m => (
                    <option key={m.raw_name} value={m.display_name}>{m.display_name}</option>
                  ))}
                </select>
              </div>
            )}

            {provenance.embedding_model && <ProvenanceChip source={provenance.embedding_model} />}

            {/* Model picker from configured providers */}
            {draft.embedding_backend === 'openai-compatible' && allModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Pick from configured providers:
                </label>
                <ModelSelect
                  value={draft.embedding_model || ''}
                  onChange={(modelId) => {
                    setEmbeddingModelInput(modelId);
                    updateDraft({ embedding_model: modelId });
                  }}
                  models={allModels}
                  showTier={true}
                  showContext={false}
                  placeholder="— Select from providers —"
                />
              </div>
            )}

            {/* OpenAI-compatible specific fields */}
            {draft.embedding_backend === 'openai-compatible' && (
              <div className="mt-4 space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <label className="text-[9px] font-semibold text-slate-600 mb-1 block">API Endpoint URL</label>
                  <input
                    type="text"
                    value={embeddingCompatibleUrl}
                    onChange={(e) => setEmbeddingCompatibleUrl(e.target.value)}
                    onBlur={() => updateDraft({ embedding_compatible_url: embeddingCompatibleUrl })}
                    placeholder="http://localhost:8000/v1"
                    className="w-full px-3 py-2 rounded-md text-xs font-mono"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="text-[9px] font-semibold text-slate-600 mb-1 block">API Key (optional)</label>
                  <input
                    type="password"
                    value={embeddingCompatibleKey}
                    onChange={(e) => setEmbeddingCompatibleKey(e.target.value)}
                    onBlur={() => updateDraft({ embedding_compatible_key: embeddingCompatibleKey })}
                    placeholder="sk-..."
                    className="w-full px-3 py-2 rounded-md text-xs font-mono"
                    style={inputStyle}
                  />
                </div>
              </div>
            )}
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
            const isSelected = draft.vector_backend === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => updateDraft({ vector_backend: opt.value as MemoryVectorBackend, vector_store: opt.value })}
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
                onClick={() => updateDraft({ context_aware: !draft.context_aware })}
                className={`relative w-9 h-5 rounded-full transition-colors ${
                  draft.context_aware ? 'bg-blue-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    draft.context_aware ? 'translate-x-4' : ''
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
                onClick={() => updateDraft({ auto_sync: !draft.auto_sync })}
                className={`relative w-9 h-5 rounded-full transition-colors ${
                  draft.auto_sync ? 'bg-blue-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    draft.auto_sync ? 'translate-x-4' : ''
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
                value={syncIntervalInput}
                onChange={(e) => setSyncIntervalInput(e.target.value)}
                onBlur={() => {
                  const parsed = Math.max(10, parseInt(syncIntervalInput, 10) || 60);
                  setSyncIntervalInput(String(parsed));
                  updateDraft({ auto_sync_interval: parsed });
                }}
                min={10}
                max={3600}
                disabled={!draft.auto_sync}
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
                value={ttlDaysInput}
                onChange={(e) => setTtlDaysInput(e.target.value)}
                onBlur={() => {
                  const parsed = Math.max(1, parseInt(ttlDaysInput, 10) || 30);
                  setTtlDaysInput(String(parsed));
                  updateDraft({ ttl_days: parsed });
                }}
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

      {/* ── Sample Configuration ──────────────────────────── */}
      <ModelConfigSample
        llmBackend={draft.llm_backend}
        llmModel={draft.llm_model}
        embeddingBackend={draft.embedding_backend}
        embeddingModel={draft.embedding_model}
        type="memory"
      />

      {/* ── Save Settings Button ──────────────────────────── */}
      {hasChanges && (
        <section className="sticky bottom-0 bg-surface-container-low border-t border-slate-200 py-4 mt-8 flex justify-end gap-3 z-10">
          <button
            onClick={() => {
              setDraft({ ...DEFAULTS, ...memory });
              setLlmModelInput(memory.llm_model ?? '');
              setEmbeddingModelInput(memory.embedding_model ?? '');
              setSyncIntervalInput(String(memory.auto_sync_interval ?? 60));
              setTtlDaysInput(String(memory.ttl_days ?? 30));
              setLlmCompatibleUrl((memory.llm_compatible_url as string) ?? '');
              setLlmCompatibleKey((memory.llm_compatible_key as string) ?? '');
              setEmbeddingCompatibleUrl((memory.embedding_compatible_url as string) ?? '');
              setEmbeddingCompatibleKey((memory.embedding_compatible_key as string) ?? '');
              setHasChanges(false);
            }}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 px-6 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-all disabled:opacity-75"
          >
            {isSaving && <span className="material-symbols-outlined text-sm animate-spin">progress_activity</span>}
            {isSaving ? 'Saving...' : 'Save Memory Settings'}
          </button>
        </section>
      )}

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
              <span>{String(effective.auto_sync_interval)}</span>
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}