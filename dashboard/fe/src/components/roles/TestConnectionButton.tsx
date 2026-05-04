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
  fix?: string;
  category?: string;
  resolved_model?: string;
  raw_output?: string;
}

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  auth:     { label: 'Auth',     color: '#f59e0b' },
  protocol: { label: 'Protocol', color: '#ef4444' },
  model:    { label: 'Model ID', color: '#8b5cf6' },
  quota:    { label: 'Quota',    color: '#f97316' },
  network:  { label: 'Network',  color: '#3b82f6' },
  timeout:  { label: 'Timeout',  color: '#6b7280' },
  install:  { label: 'Install',  color: '#ef4444' },
  internal: { label: 'Internal', color: '#ef4444' },
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
      const data = await apiPost<TestResult>(
        `/models/${version}/test`,
        {}
      );
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
            opacity: loading ? 0.7 : 1,
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
            {result.resolved_model && (
              <span className="font-normal text-[10px] opacity-60 ml-1">via {result.resolved_model}</span>
            )}
          </div>
        )}

        {result && !isOk && cat && (
          <span
            className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider"
            style={{ background: cat.color + '22', color: cat.color }}
          >
            {cat.label}
          </span>
        )}
      </div>

      {/* ── Failure diagnostic panel ── */}
      {result && !isOk && (
        <div
          className="rounded-lg p-3 text-[11px] fade-in"
          style={{
            background: 'var(--color-surface-raised, #1a1a1a)',
            border: '1px solid #3f3f3f',
            maxWidth: '480px',
          }}
        >
          {/* Main error message */}
          <div className="flex items-start gap-2 text-red-400 font-medium leading-snug">
            <span className="material-symbols-outlined text-sm shrink-0 mt-0.5">error</span>
            <span>{result.error || 'Connection failed'}</span>
          </div>

          {/* Fix hint */}
          {result.fix && (
            <div
              className="mt-2 pt-2 flex items-start gap-2 leading-snug"
              style={{
                borderTop: '1px solid #2a2a2a',
                color: 'var(--color-text-dim, #888)',
              }}
            >
              <span className="material-symbols-outlined text-sm shrink-0 mt-0.5 text-yellow-500">
                lightbulb
              </span>
              <pre
                className="whitespace-pre-wrap font-sans"
                style={{ margin: 0 }}
              >
                {result.fix}
              </pre>
            </div>
          )}

          {/* Resolved model + latency */}
          <div className="mt-2 flex items-center gap-3 opacity-50 text-[10px]">
            {result.resolved_model && <span>resolved: {result.resolved_model}</span>}
            {result.latency_ms !== undefined && <span>{result.latency_ms}ms</span>}
          </div>

          {/* Raw output toggle */}
          {result.raw_output && (
            <div className="mt-2 pt-2" style={{ borderTop: '1px solid #2a2a2a' }}>
              <button
                type="button"
                onClick={() => setShowRaw(v => !v)}
                className="flex items-center gap-1 text-[10px] opacity-60 hover:opacity-100 transition-opacity"
              >
                <span className="material-symbols-outlined text-xs">
                  {showRaw ? 'expand_less' : 'expand_more'}
                </span>
                {showRaw ? 'Hide' : 'Show'} raw output
              </button>
              {showRaw && (
                <pre
                  className="mt-2 p-2 rounded text-[10px] overflow-x-auto whitespace-pre-wrap break-all"
                  style={{
                    background: '#0d0d0d',
                    color: '#ccc',
                    maxHeight: '200px',
                    overflowY: 'auto',
                  }}
                >
                  {result.raw_output}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
