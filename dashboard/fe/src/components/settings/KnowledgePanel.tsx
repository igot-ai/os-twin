'use client';

import { useEffect, useMemo, useState } from 'react';
import type { KnowledgeSettings, ModelInfo } from '@/types/settings';
import { ModelSelect } from '@/components/settings/ModelSelect';

export interface KnowledgePanelProps {
  knowledge: KnowledgeSettings;
  onUpdate: (value: Partial<KnowledgeSettings>) => void | Promise<void>;
  allModels: ModelInfo[];
}

// ── Suggested Hugging Face embedding models ─────────────────────────────────

interface EmbeddingSuggestion {
  id: string;
  dim: number;
  description: string;
}

const SUGGESTED_EMBEDDINGS: EmbeddingSuggestion[] = [
  { id: 'BAAI/bge-small-en-v1.5',                       dim: 384,  description: 'Recommended default — fast, good quality' },
  { id: 'BAAI/bge-base-en-v1.5',                        dim: 768,  description: 'Higher quality, ~3x slower' },
  { id: 'BAAI/bge-large-en-v1.5',                       dim: 1024, description: 'Best quality, ~10x slower than small' },
  { id: 'sentence-transformers/all-MiniLM-L6-v2',       dim: 384,  description: 'Classic baseline, smaller footprint' },
  { id: 'intfloat/e5-small-v2',                         dim: 384,  description: 'Strong on multilingual, instruction-tuned' },
  { id: 'intfloat/multilingual-e5-base',                dim: 768,  description: 'Multilingual with broader coverage' },
];

// ── Defaults (match backend KnowledgeSettings defaults) ─────────────────────

const DEFAULTS: KnowledgeSettings = {
  llm_model: '',
  embedding_model: '',
  embedding_dimension: 384,
};

// ── Component ───────────────────────────────────────────────────────────────

export function KnowledgePanel({ knowledge, onUpdate, allModels }: KnowledgePanelProps) {
  const effective = { ...DEFAULTS, ...knowledge };

  const [embedInput, setEmbedInput] = useState(effective.embedding_model);
  const [savingMsg, setSavingMsg] = useState<string | null>(null);
  const [savingError, setSavingError] = useState(false);

  // Keep local input in sync if external settings change (e.g. WS broadcast)
  useEffect(() => {
    setEmbedInput(effective.embedding_model);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effective.embedding_model]);

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

  const handleLlmChange = async (model: string) => {
    setSavingMsg('Saving…');
    setSavingError(false);
    try {
      await onUpdate({ llm_model: model });
      flashSavedMessage('Saved');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'unknown error';
      flashSavedMessage(`Save failed: ${msg}`, true);
    }
  };

  const commitEmbedding = async (modelId: string) => {
    if (modelId === effective.embedding_model) return;
    setSavingMsg('Saving…');
    setSavingError(false);
    try {
      const match = SUGGESTED_EMBEDDINGS.find((s) => s.id === modelId);
      const dim = match?.dim ?? effective.embedding_dimension;
      await onUpdate({ embedding_model: modelId, embedding_dimension: dim });
      flashSavedMessage('Saved — restart dashboard to apply', false, 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'unknown error';
      flashSavedMessage(`Save failed: ${msg}`, true);
    }
  };

  const handleEmbedBlur = () => {
    void commitEmbedding(embedInput);
  };

  const handleEmbedKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  const handleSuggestionClick = (id: string) => {
    setEmbedInput(id);
    void commitEmbedding(id);
  };

  // Used only by the embedding text input
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
            SYSTEM_ADMIN
          </span>
          <span className="text-xs text-on-surface-variant">/ configuration / knowledge-models</span>
        </div>
        <h2 className="text-2xl font-extrabold tracking-tight text-on-surface mb-1">
          Knowledge Models
        </h2>
        <p className="text-sm text-on-surface-variant">
          Configure the LLM and embedding models used by the knowledge service for entity
          extraction, query answering, and document indexing. Settings map to{' '}
          <code className="font-mono text-[10px] bg-slate-100 px-1 py-0.5 rounded">
            KNOWLEDGE_*
          </code>{' '}
          environment variables.
        </p>
      </div>

      {/* ── Section 1: LLM Model ────────────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-blue-600 text-lg">psychology</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">LLM Model</h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">KNOWLEDGE_LLM_MODEL</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <p className="text-[10px] text-slate-500 mb-3">
            Used for entity extraction during ingest and answer aggregation in{' '}
            <code className="font-mono text-[10px] bg-slate-100 px-1 py-0.5 rounded">summarized</code>{' '}
            query mode. Pick any chat-capable model from your configured providers, or leave on
            server default.
          </p>
          <ModelSelect
            value={effective.llm_model}
            onChange={handleLlmChange}
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
              {effective.llm_model || '(server default)'}
            </code>
          </p>
        </div>
      </section>

      {/* ── Section 2: Embedding Model ──────────────────────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-purple-600 text-lg">layers</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">
            Embedding Model
          </h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">
            KNOWLEDGE_EMBEDDING_MODEL
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
          <p className="text-[10px] text-slate-500">
            Hugging Face model id used by sentence-transformers for vector indexing and retrieval.
            Changing this requires a <strong>fresh namespace</strong> — existing vectors won&apos;t
            be re-embedded.
          </p>

          <div>
            <label className="text-[9px] text-slate-400 mb-1 block">Hugging Face model id:</label>
            <input
              type="text"
              value={embedInput}
              onChange={(e) => setEmbedInput(e.target.value)}
              onBlur={handleEmbedBlur}
              onKeyDown={handleEmbedKeyDown}
              placeholder="BAAI/bge-small-en-v1.5"
              className="w-full px-3 py-2 rounded-md text-xs font-mono"
              style={inputStyle}
            />
          </div>

          <details className="group">
            <summary className="flex items-center gap-1.5 cursor-pointer text-[10px] text-blue-600 hover:text-blue-700 select-none">
              <span className="material-symbols-outlined text-sm group-open:rotate-180 transition-transform">
                expand_more
              </span>
              <span className="font-semibold uppercase tracking-wider">
                Suggested embeddings
              </span>
            </summary>
            <div className="mt-2 space-y-1.5">
              {SUGGESTED_EMBEDDINGS.map((s) => {
                const isActive = embedInput === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => handleSuggestionClick(s.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${
                      isActive
                        ? 'bg-purple-50 border border-purple-400 text-purple-700'
                        : 'bg-white border border-slate-200 text-slate-600 hover:border-purple-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <code className="font-mono text-[10px]">{s.id}</code>
                      <span className="text-[9px] text-slate-400 font-mono ml-2 whitespace-nowrap">
                        dim {s.dim}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">{s.description}</p>
                  </button>
                );
              })}
            </div>
          </details>

          <p className="text-[10px] text-slate-400">
            Currently effective:{' '}
            <code className="font-mono text-[10px] text-slate-600">
              {effective.embedding_model || '(server default)'}
            </code>
          </p>
        </div>
      </section>

      {/* ── Section 3: Embedding Dimension (read-only) ──────── */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="material-symbols-outlined text-emerald-600 text-lg">straighten</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">
            Embedding Dimension
          </h3>
          <span className="text-[9px] text-slate-400 ml-auto font-mono">read-only</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <p className="text-[10px] text-slate-500 mb-3">
            Fixed by the embedding model above. Existing namespaces store this value at creation
            time; changing the embedding model later will not retro-update old vectors.
          </p>
          <div className="flex items-baseline gap-2">
            <code className="text-2xl font-extrabold font-mono text-slate-900">
              {effective.embedding_dimension}
            </code>
            <span className="text-[10px] text-slate-400">dimensions</span>
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
