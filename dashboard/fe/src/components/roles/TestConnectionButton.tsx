'use client';

import { useState } from 'react';
import { apiPost } from '@/lib/api-client';

interface TestConnectionButtonProps {
  version: string;
}

interface TestResult {
  status: string;
  latency_ms?: number;
  error?: string;
  output?: string;
  category?: string;
  fix?: string;
  raw_output?: string;
  resolved_model?: string;
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  protocol: { label: 'Protocol', color: '#f59e0b' },
  auth:     { label: 'Auth',     color: '#ef4444' },
  model:    { label: 'Model',    color: '#8b5cf6' },
  quota:    { label: 'Quota',    color: '#f97316' },
  network:  { label: 'Network',  color: '#3b82f6' },
  timeout:  { label: 'Timeout',  color: '#6b7280' },
  install:  { label: 'Install',  color: '#ec4899' },
  unknown:  { label: 'Error',    color: '#6b7280' },
};

export default function TestConnectionButton({ version }: TestConnectionButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const handleTest = async () => {
    if (!version) return;
    setLoading(true);
    setResult(null);
    setShowRaw(false);
    try {
      const data = await apiPost<TestResult>(`/models/${version}/test`, {});
      setResult(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Connection failed';
      setResult({ status: 'fail', latency_ms: 0, error: message, category: 'unknown' });
    } finally {
      setLoading(false);
    }
  };

  const isOk = result?.status === 'ok';
  const cat = result?.category ? CATEGORY_LABELS[result.category] ?? CATEGORY_LABELS.unknown : null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleTest}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
          style={{
            background: 'transparent',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-main)',
            opacity: loading ? 0.7 : 1
          }}
        >
          <span className={`material-symbols-outlined text-base ${loading ? 'animate-spin' : ''}`}>
            {loading ? 'refresh' : 'electrical_services'}
          </span>
          {loading ? 'Testing...' : 'Test Connection'}
        </button>

        {result && isOk && (
          <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 fade-in">
            <span className="material-symbols-outlined text-base">check_circle</span>
            OK — {result.latency_ms}ms
          </div>
        )}

        {result && !isOk && cat && (
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
            style={{ background: cat.color + '22', color: cat.color, border: `1px solid ${cat.color}44` }}
          >
            {cat.label}
          </span>
        )}
      </div>

      {result && !isOk && (
        <div className="flex flex-col gap-1 text-[11px] fade-in" style={{ maxWidth: 420 }}>
          <div className="flex items-start gap-1.5 font-semibold text-red-600">
            <span className="material-symbols-outlined text-base shrink-0">error</span>
            <span className="break-words">{result.error || 'Connection failed'}</span>
          </div>

          {result.fix && (
            <div className="flex items-start gap-1.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              <span className="material-symbols-outlined text-base shrink-0">lightbulb</span>
              <span className="break-words whitespace-pre-wrap">{result.fix}</span>
            </div>
          )}

          {result.raw_output && result.raw_output !== result.error && (
            <button
              type="button"
              onClick={() => setShowRaw(r => !r)}
              className="self-start text-[10px] underline mt-0.5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              {showRaw ? 'Hide raw output' : 'Show raw output'}
            </button>
          )}

          {showRaw && result.raw_output && (
            <pre
              className="text-[10px] p-2 rounded overflow-x-auto whitespace-pre-wrap break-all mt-0.5"
              style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)', maxHeight: 160 }}
            >
              {result.raw_output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
