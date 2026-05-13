'use client';

import { useState } from 'react';

interface ModelConfigSampleProps {
  llmBackend?: string;
  llmModel?: string;
  embeddingBackend?: string;
  embeddingModel?: string;
  embeddingDimension?: number;
  type: 'memory' | 'knowledge';
}

export function ModelConfigSample({
  llmBackend,
  llmModel,
  embeddingBackend,
  embeddingModel,
  embeddingDimension,
  type,
}: ModelConfigSampleProps) {
  const [copied, setCopied] = useState(false);

  const envPrefix = type === 'memory' ? 'MEMORY' : 'KNOWLEDGE';

  const sampleCode = `# ${type === 'memory' ? 'Memory' : 'Knowledge'} Model Configuration
# Add these to your ~/.ostwin/.env file

# Processing Model (LLM)
${envPrefix}_LLM_BACKEND=${llmBackend || 'ollama'}
${envPrefix}_LLM_MODEL=${llmModel || 'llama3.2'}

# Embedding Model
${envPrefix}_EMBEDDING_BACKEND=${embeddingBackend || 'ollama'}
${envPrefix}_EMBEDDING_MODEL=${embeddingModel || 'leoipulsar/harrier-0.6b'}

# Embedding Dimension (applied globally, must match all namespaces)
OSTWIN_EMBEDDING_DIMENSION=${embeddingDimension || 768}

# For OpenAI-Compatible backend, also set:
# ${envPrefix}_LLM_COMPATIBLE_URL=http://localhost:8000/v1
# ${envPrefix}_LLM_COMPATIBLE_KEY=sk-...
# ${envPrefix}_EMBEDDING_COMPATIBLE_URL=http://localhost:8000/v1
# ${envPrefix}_EMBEDDING_COMPATIBLE_KEY=sk-...`;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sampleCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-6 border border-slate-200 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-slate-500 text-sm">code</span>
          <span className="text-xs font-semibold text-slate-600">Environment Variables</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
        >
          <span className="material-symbols-outlined text-sm">{copied ? 'check' : 'content_copy'}</span>
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="p-4 text-[11px] font-mono text-slate-700 bg-slate-50/50 overflow-x-auto leading-relaxed">
        <code>{sampleCode}</code>
      </pre>
    </div>
  );
}
