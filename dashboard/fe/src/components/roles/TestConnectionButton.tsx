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

const CATEGORY_META: Record<string, { label: string; color: string; bg: string }> = {
  protocol: { label: 'Protocol', color: '#d97706', bg: '#fef3c7' },
  auth:     { label: 'Auth',     color: '#dc2626', bg: '#fee2e2' },
  model:    { label: 'Model',    color: '#7c3aed', bg: '#ede9fe' },
  quota:    { label: 'Quota',    color: '#ea580c', bg: '#ffedd5' },
  network:  { label: 'Network',  color: '#2563eb', bg: '#dbeafe' },
  timeout:  { label: 'Timeout',  color: '#6b7280', bg: '#f3f4f6' },
  install:  { label: 'Install',  color: '#db2777', bg: '#fce7f3' },
  unknown:  { label: 'Error',    color: '#6b7280', bg: '#f3f4f6' },
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
  const cat = result?.category ? (CATEGORY_META[result.category] ?? CATEGORY_META.unknown) : null;

  return (
    <div className="flex flex-col gap-2" style={{ maxWidth: 460 }}>
      {/* ── Button row ── */}
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
          {loading ? 'Testing…' : 'Test Connection'}
        </button>

        {result && isOk && (
          <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-600 fade-in">
            <span className="material-symbols-outlined text-base">check_circle</span>
            OK — {result.latency_ms}ms
          </div>
        )}
      </div>

      {/* ── Diagnostic panel ── */}
      {result && !isOk && (
        <div
          className="fade-in rounded-xl p-3 flex flex-col gap-2"
          style={{
            border: `1px solid ${cat?.color ?? '#dc2626'}33`,
            background: cat?.bg ?? '#fee2e2',
          }}
        >
          {/* Category badge + error message */}
          <div className="flex items-start gap-2">
            <span
              className="material-symbols-outlined text-base shrink-0 mt-px"
              style={{ color: cat?.color ?? '#dc2626' }}
            >
              error
            </span>
            <div className="flex flex-col gap-0.5 flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {cat && (
                  <span
                    className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                    style={{ background: cat.color + '22', color: cat.color }}
                  >
                    {cat.label}
                  </span>
                )}
                <span className="text-[11px] font-semibold break-words" style={{ color: cat?.color ?? '#dc2626' }}>
                  {result.error || 'Connection failed'}
                </span>
              </div>
            </div>
          </div>

          {/* Fix hint */}
          {result.fix && (
            <div
              className="flex items-start gap-2 text-[11px] rounded-lg px-2.5 py-2"
              style={{
                background: 'rgba(255,255,255,0.6)',
                color: 'var(--color-text-main)',
              }}
            >
              <span className="material-symbols-outlined text-base shrink-0 mt-px" style={{ color: cat?.color ?? '#6b7280' }}>
                lightbulb
              </span>
              <span className="break-words whitespace-pre-wrap leading-relaxed">{result.fix}</span>
            </div>
          )}

          {/* Raw output toggle */}
          {result.raw_output && result.raw_output !== result.error && (
            <button
              type="button"
              onClick={() => setShowRaw(r => !r)}
              className="self-start text-[10px] font-medium underline-offset-2 underline"
              style={{ color: cat?.color ?? '#6b7280' }}
            >
              {showRaw ? 'Hide raw output' : 'Show raw output'}
            </button>
          )}

          {showRaw && result.raw_output && (
            <pre
              className="text-[10px] p-2.5 rounded-lg overflow-auto whitespace-pre-wrap break-all"
              style={{
                background: 'rgba(0,0,0,0.06)',
                color: 'var(--color-text-main)',
                maxHeight: 180,
                fontFamily: 'monospace',
              }}
            >
              {result.raw_output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
