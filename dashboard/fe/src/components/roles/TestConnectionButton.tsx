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
}

export default function TestConnectionButton({ version }: TestConnectionButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);

  const handleTest = async () => {
    if (!version) return;
    setLoading(true);
    setResult(null);
    try {
      const data = await apiPost<TestResult>(
        `/models/${version}/test`,
        {}
      );
      setResult(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Connection failed';
      setResult({ status: 'fail', latency_ms: 0, error: message });
    } finally {
      setLoading(false);
    }
  };

  const isOk = result?.status === 'ok';

  return (
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

      {result && !isOk && (
        <div className="flex items-center gap-1.5 text-[11px] font-bold text-red-600 fade-in max-w-[240px]">
          <span className="material-symbols-outlined text-base shrink-0">error</span>
          <span className="truncate">{result.error || 'Connection failed'}</span>
        </div>
      )}
    </div>
  );
}
