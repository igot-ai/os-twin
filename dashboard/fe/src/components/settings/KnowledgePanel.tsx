'use client';

import { useEffect, useMemo, useState } from 'react';
import type { KnowledgeSettings, MemoryEmbeddingBackend, ModelInfo } from '@/types/settings';
import { ModelSelect } from '@/components/settings/ModelSelect';
import { ProviderIcon } from './ProviderIcon';

export interface KnowledgePanelProps {
  knowledge: KnowledgeSettings;
  onUpdate: (value: Partial<KnowledgeSettings>) => void | Promise<void>;
  allModels: ModelInfo[];
}

// ── Backend option definitions (synchronised with MemoryPanel) ──────────────

interface BackendOption {
  value: string;
  label: string;
  description: string;
  requiresKey?: string;
  icon: string;
}

const LLM_BACKENDS: BackendOption[] = [
  { value: '',          label: '— Use server default —', description: 'Uses env-var / hardcoded default', icon: 'settings' },
  { value: 'ollama',    label: 'Ollama (Local)',          description: 'Local Ollama server', icon: 'dns' },
  { value: 'openai-compatible', label: 'OpenAI-Compatible', description: 'Any OpenAI-compatible API server', icon: 'api' },
];

const EMBEDDING_BACKENDS: BackendOption[] = [
  { value: '',                    label: '— Use server default —',     description: 'Uses env-var / hardcoded default', icon: 'settings' },
  { value: 'ollama',               label: 'Ollama (Local)',             description: 'Local Ollama embedding server', icon: 'dns' },
  { value: 'openai-compatible',    label: 'OpenAI-Compatible',          description: 'Any OpenAI-compatible embedding API', icon: 'api' },
];

// ── Recommended models per backend (synchronised with MemoryPanel) ──────────

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

const DEFAULTS: KnowledgeSettings = {
  knowledge_llm_backend: '',
  knowledge_llm_model: '',
  knowledge_embedding_backend: '',
  knowledge_embedding_model: '',
  knowledge_embedding_dimension: 768,
};

// ── Component ───────────────────────────────────────────────────────────────

export function KnowledgePanel({ knowledge, onUpdate, allModels }: KnowledgePanelProps) {
  const effective = { ...DEFAULTS, ...knowledge };

  const [llmModelInput, setLlmModelInput] = useState(effective.knowledge_llm_model);
  const [embedModelInput, setEmbedModelInput] = useState(effective.knowledge_embedding_model);
  const [savingMsg, setSavingMsg] = useState<string | null>(null);
  const [savingError, setSavingError] = useState(false);
  
  // OpenAI-compatible specific fields
  const [llmCompatibleUrl, setLlmCompatibleUrl] = useState(effective.knowledge_llm_compatible_url ?? '');
  const [llmCompatibleKey, setLlmCompatibleKey] = useState(effective.knowledge_llm_compatible_key ?? '');
  const [embeddingCompatibleUrl, setEmbeddingCompatibleUrl] = useState(effective.knowledge_embedding_compatible_url ?? '');
  const [embeddingCompatibleKey, setEmbeddingCompatibleKey] = useState(effective.knowledge_embedding_compatible_key ?? '');

  // Keep local inputs in sync if external settings change (e.g. WS broadcast)
  useEffect(() => {
    setLlmModelInput(effective.knowledge_llm_model);
  }, [effective.knowledge_llm_model]);

  useEffect(() => {
    setEmbedModelInput(effective.knowledge_embedding_model);
  }, [effective.knowledge_embedding_model]);

  // Filter out obvious embedding-only models from chat picker
  const chatModels = useMemo(
    () => allModels.filter((m) => !m.id.toLowerCase().includes('embed')),
    [allModels],
  );

  const flashSavedMessage = (msg: string, isError = false, ttl = 1800) => {
    setSavingMsg(msg);
    setSavingError(isError);
    if (!isError) {
      setTimeout(() => setSavingMsg(null), ttl);
    }
  };

  const save = async (patch: Partial<KnowledgeSettings>) => {
    setSavingMsg('Saving…');
    setSavingError(false);
    try {
      await onUpdate(patch);
      flashSavedMessage('Saved — restart dashboard to apply', false, 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'unknown error';
      flashSavedMessage(`Save failed: ${msg}`, true);
    }
  };

  // ── LLM handlers ────────────────────────────────────────────────────────

  const handleLlmBackendChange = (backend: string) => {
    const suggestions = LLM_MODEL_SUGGESTIONS[backend] ?? [];
    const model = suggestions[0]?.model ?? '';
    void save({ knowledge_llm_backend: backend, knowledge_llm_model: model });
    setLlmModelInput(model);
  };

  const handleLlmModelSelect = (model: string) => {
    void save({ knowledge_llm_model: model });
    setLlmModelInput(model);
  };

  const commitLlmModelInput = () => {
    if (llmModelInput !== effective.knowledge_llm_model) {
      void save({ knowledge_llm_model: llmModelInput });
    }
  };

  // ── Embedding handlers ──────────────────────────────────────────────────

  const handleEmbedBackendChange = (backend: string) => {
    const suggestions = EMBEDDING_MODEL_SUGGESTIONS[backend] ?? [];
    const model = suggestions[0]?.model ?? '';
    void save({
      knowledge_embedding_backend: backend as MemoryEmbeddingBackend | '',
      knowledge_embedding_model: model,
      knowledge_embedding_dimension: 768,
    });
    setEmbedModelInput(model);
  };

  const handleEmbedModelSelect = (model: string) => {
    void save({ knowledge_embedding_model: model, knowledge_embedding_dimension: 768 });
    setEmbedModelInput(model);
  };

  const commitEmbedModelInput = () => {
    if (embedModelInput !== effective.knowledge_embedding_model) {
      void save({ knowledge_embedding_model: embedModelInput, knowledge_embedding_dimension: 768 });
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────

  const inputStyle = {
    background: '#f1f5f9',
    border: '1px solid #e2e8f0',
    color: '#0f172a',
  };

  const llmSuggestions = LLM_MODEL_SUGGESTIONS[effective.knowledge_llm_backend] ?? [];
  const embedSuggestions = EMBEDDING_MODEL_SUGGESTIONS[effective.knowledge_embedding_backend] ?? [];

  return (
    <div className="space-y-8">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-primary bg-primary-container px-2 py-0.5 rounded">
            SYSTEM_ADMIN
          </span>
          <span className="text-xs text-on-surface-variant">/ configuration / knowledge-models</span>
        </div>
        <h2 className="text-2xl font-extrabold tracking-tight text-on-surface mb-1">
          Knowledge Models
        </h2>
        <p className="text-sm text-on-surface-variant">
          Configure the LLM and embedding backends used by the knowledge service for entity
          extraction, query answering, and document indexing. All embeddings are normalised to{' '}
          <code className="font-mono text-[10px] bg-slate-100 px-1 py-0.5 rounded">768</code>{' '}
          dimensions.
        </p>
      </div>

      {/* ── Section 1: LLM Backend ───────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">psychology</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Processing Model</h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">knowledge_llm_backend / knowledge_llm_model</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* LLM Backend Selector */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              LLM Backend
            </label>
            <div className="space-y-1.5">
              {LLM_BACKENDS.map((b) => {
                const isActive = effective.knowledge_llm_backend === b.value;
                return (
                  <button
                    key={b.value}
                    type="button"
                    onClick={() => handleLlmBackendChange(b.value)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all ${
                      isActive
                        ? 'bg-blue-50 border-2 border-blue-500 shadow-sm'
                        : 'bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50/30 cursor-pointer'
                    }`}
                  >
                    <ProviderIcon provider={b.value} size={16} className={isActive ? '' : 'opacity-50'} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`text-xs font-semibold ${isActive ? 'text-blue-700' : 'text-slate-700'}`}>
                          {b.label}
                        </span>
                        {!b.requiresKey && b.value !== '' && (
                          <span className="text-[8px] font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            Local
                          </span>
                        )}
                      </div>
                      <p className="text-[9px] text-slate-400 truncate">{b.description}</p>
                    </div>
                    {isActive && (
                      <span className="material-symbols-outlined text-blue-600 text-sm">check_circle</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* LLM Model Selector */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
              Model
            </label>
            {/* Suggested models for the selected backend */}
            {effective.knowledge_llm_backend && llmSuggestions.length > 0 && (
              <div className="space-y-1 mb-3">
                {llmSuggestions.map((s) => {
                  const isActive = llmModelInput === s.model;
                  return (
                    <button
                      key={s.model}
                      type="button"
                      onClick={() => handleLlmModelSelect(s.model)}
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
                onBlur={commitLlmModelInput}
                onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
                placeholder="e.g. llama3.2"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={inputStyle}
              />
            </div>
            
            {/* Model dropdown from configured providers */}
            {chatModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Or pick from configured providers:
                </label>
                <ModelSelect
                  value={effective.knowledge_llm_model || ''}
                  onChange={(m) => handleLlmModelSelect(m)}
                  models={chatModels}
                  showTier={true}
                  showContext={true}
                  placeholder="— Select from providers —"
                />
              </div>
            )}
            
            {/* Model dropdown from configured providers */}
            {allModels.length > 0 && (
              <div className="mt-3">
                <label className="text-[9px] text-slate-500 mb-2 block">
                  Or pick from configured providers:
                </label>
                <ModelSelect
                  value={effective.knowledge_embedding_model || ''}
                  onChange={(m) => handleEmbedModelSelect(m)}
                  models={allModels}
                  showTier={true}
                  showContext={false}
                  placeholder="— Select from providers —"
                />
              </div>
            )}
            
            {/* OpenAI-compatible specific fields */}
            {effective.knowledge_embedding_backend === 'openai-compatible' && (
              <div className="mt-4 space-y-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div>
                  <label className="text-[9px] font-semibold text-slate-600 mb-1 block">API Endpoint URL</label>
                  <input
                    type="text"
                    value={embeddingCompatibleUrl}
                    onChange={(e) => setEmbeddingCompatibleUrl(e.target.value)}
                    onBlur={() => save({ knowledge_embedding_compatible_url: embeddingCompatibleUrl })}
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
                    onBlur={() => save({ knowledge_embedding_compatible_key: embeddingCompatibleKey })}
                    placeholder="sk-..."
                    className="w-full px-3 py-2 rounded-md text-xs font-mono"
                    style={inputStyle}
                  />
                </div>
              </div>
            )}
            
            <p className="text-[10px] text-slate-400 mt-3">
              All vectors are normalised to <strong>768 dimensions</strong>. Changing backend requires a{' '}
              <strong>fresh namespace</strong>.
            </p>
          </div>
        </div>
      </section>

      {/* ── Section 3: Embedding Dimension (read-only) ──────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-emerald-600 text-lg">straighten</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">
            Embedding Dimension
          </h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">fixed: 768</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <p className="text-[10px] text-slate-500 mb-3">
            All embedding backends produce vectors normalised to <strong>768 dimensions</strong> for
            consistency. This is enforced globally and cannot be changed.
          </p>
          <div className="flex items-baseline gap-2">
            <code className="text-2xl font-extrabold font-mono text-slate-900">768</code>
            <span className="text-[10px] text-slate-400">dimensions (fixed)</span>
          </div>
        </div>
      </section>

      {/* ── Save status toast ───────────────────────────────── */}
      {savingMsg && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-6 right-6 px-4 py-2 rounded-lg text-xs font-semibold shadow-lg z-50 ${
            savingError
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-blue-50 text-blue-700 border border-blue-200'
          }`}
        >
          {savingError && (
            <span className="material-symbols-outlined text-sm align-middle mr-1">error</span>
          )}
          {savingMsg}
          {savingError && (
            <button
              type="button"
              onClick={() => setSavingMsg(null)}
              className="ml-3 text-red-500 hover:text-red-700"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default KnowledgePanel;
