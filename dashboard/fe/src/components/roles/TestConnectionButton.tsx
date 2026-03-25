'use client';

import { useState } from 'react';

interface TestConnectionButtonProps {
  version: string;
}

export default function TestConnectionButton({ version }: TestConnectionButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ status: string; latency_ms: number } | null>(null);

  const handleTest = async () => {
    if (!version) return;
    setLoading(true);
    setResult(null);
    try {
      const response = await fetch(`/api/models/${encodeURIComponent(version)}/test`, {
        method: 'POST',
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Test connection failed:', error);
      setResult({ status: 'fail', latency_ms: 0 });
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
          ✓ OK — {result.latency_ms}ms
        </div>
      )}

      {result && !isOk && (
        <div className="flex items-center gap-1.5 text-[11px] font-bold text-red-600 fade-in">
          <span className="material-symbols-outlined text-base">error</span>
          Connection Failed
        </div>
      )}
    </div>
  );
}
