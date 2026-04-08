'use client';

import { ProvenanceChip } from './ProvenanceChip';
import type { MemorySettings } from '@/types/settings';

export interface MemoryPanelProps {
  memory: MemorySettings;
  provenance?: Record<string, string>;
  onUpdate: (value: Partial<MemorySettings>) => void;
}

export function MemoryPanel({ memory, provenance = {}, onUpdate }: MemoryPanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Vector Store
        </label>
        <input
          type="text"
          value={memory.vector_store || ''}
          onChange={(e) => onUpdate({ vector_store: e.target.value })}
          placeholder="zvec"
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        />
        {provenance.vector_store && <ProvenanceChip source={provenance.vector_store} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          Embedding Model
        </label>
        <input
          type="text"
          value={memory.embedding_model || ''}
          onChange={(e) => onUpdate({ embedding_model: e.target.value })}
          placeholder="microsoft/harrier-oss-v1-0.6b"
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        />
        {provenance.embedding_model && <ProvenanceChip source={provenance.embedding_model} />}
      </div>

      <div>
        <label className="text-[10px] font-semibold uppercase tracking-wider mb-2 block text-slate-500">
          TTL (days)
        </label>
        <input
          type="number"
          value={memory.ttl_days || 30}
          onChange={(e) => onUpdate({ ttl_days: parseInt(e.target.value, 10) || 30 })}
          min={1}
          max={365}
          className="w-full px-3 py-2 rounded-md text-xs font-mono"
          style={{
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            color: '#0f172a',
          }}
        />
        {provenance.ttl_days && <ProvenanceChip source={provenance.ttl_days} />}
        <p className="text-[9px] mt-1 text-slate-500">
          Memory entries older than TTL will be automatically deleted
        </p>
      </div>
    </div>
  );
}
