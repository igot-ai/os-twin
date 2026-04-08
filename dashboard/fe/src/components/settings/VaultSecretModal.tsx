'use client';

import { useState } from 'react';

export interface VaultSecretModalProps {
  isOpen: boolean;
  onClose: () => void;
  scope: string;
  keyName: string;
  isSet: boolean;
  onSubmit: (secret: string) => Promise<void>;
}

export function VaultSecretModal({
  isOpen,
  onClose,
  scope,
  keyName,
  isSet,
  onSubmit,
}: VaultSecretModalProps) {
  const [secret, setSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await onSubmit(secret);
      setSuccess(true);
      setSecret('');
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save secret';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: 'rgba(0, 0, 0, 0.7)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border p-6"
        style={{
          background: '#ffffff',
          borderColor: '#e2e8f0',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold" style={{ color: '#0f172a' }}>
            Vault Secret
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:opacity-80 transition-opacity text-slate-500"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        <div className="mb-4">
          <div className="text-xs font-mono text-slate-500">
            Scope: <span style={{ color: '#0f172a' }}>{scope}</span>
          </div>
          <div className="text-xs font-mono text-slate-500">
            Key: <span style={{ color: '#0f172a' }}>{keyName}</span>
          </div>
        </div>

        <div
          className="mb-4 px-3 py-2 rounded-md text-xs"
          style={{
            background: isSet ? 'rgba(22, 163, 74, 0.08)' : 'rgba(239, 68, 68, 0.1)',
            color: isSet ? '#16a34a' : 'var(--color-danger)',
          }}
        >
          {isSet ? '✓ Secret is set' : '✗ Secret not set'}
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
              Secret Value
            </label>
            <input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder="Enter secret value"
              className="w-full px-3 py-2 rounded-md text-xs font-mono"
              style={{
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                color: '#0f172a',
              }}
              required
            />
            <p className="text-[9px] mt-1 text-slate-500">
              Secret will be stored securely and never displayed
            </p>
          </div>

          {error && (
            <div className="mb-4 text-xs p-2 rounded" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
              {error}
            </div>
          )}

          {success && (
            <div className="mb-4 text-xs p-2 rounded" style={{ background: 'rgba(22, 163, 74, 0.08)', color: '#16a34a' }}>
              ✓ Secret saved successfully
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading || !secret.trim()}
              className="flex-1 px-4 py-2 rounded-md text-xs font-semibold transition-opacity"
              style={{
                background: loading ? 'var(--color-surface)' : 'rgba(37, 99, 235, 0.15)',
                color: '#2563eb',
                opacity: !secret.trim() ? 0.5 : 1,
              }}
            >
              {loading ? 'Saving...' : 'Save Secret'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md text-xs font-semibold"
              style={{
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                color: '#0f172a',
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
