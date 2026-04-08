'use client';

import { useState } from 'react';
import { useEffectiveSettings } from '@/hooks/use-settings';
import { ProvenanceChip } from './ProvenanceChip';

export interface ResolverInspectorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ResolverInspectorModal({ isOpen, onClose }: ResolverInspectorModalProps) {
  const [role, setRole] = useState('engineer');
  const [planId, setPlanId] = useState('');
  const [taskRef, setTaskRef] = useState('');

  const { data, isLoading, isError } = useEffectiveSettings(
    role,
    planId || undefined,
    taskRef || undefined
  );

  if (!isOpen) return null;

  const handleQuery = () => {
    // The useEffectiveSettings hook automatically refetches when params change
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      style={{ background: 'rgba(0, 0, 0, 0.7)' }}
      onClick={handleClose}
    >
      <div
        className="w-full max-w-2xl rounded-xl border p-6 max-h-[80vh] overflow-y-auto"
        style={{
          background: '#ffffff',
          borderColor: '#e2e8f0',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold" style={{ color: '#0f172a' }}>
            Resolver Inspector
          </h2>
          <button
            onClick={handleClose}
            className="p-1 rounded hover:opacity-80 transition-opacity text-slate-500"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        <div className="mb-4 space-y-3">
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
              Role
            </label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="engineer"
              className="w-full px-3 py-2 rounded-md text-xs font-mono"
              style={{
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                color: '#0f172a',
              }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                Plan ID (optional)
              </label>
              <input
                type="text"
                value={planId}
                onChange={(e) => setPlanId(e.target.value)}
                placeholder="PLAN-001"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={{
                  background: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  color: '#0f172a',
                }}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                Task Ref (optional)
              </label>
              <input
                type="text"
                value={taskRef}
                onChange={(e) => setTaskRef(e.target.value)}
                placeholder="EPIC-001"
                className="w-full px-3 py-2 rounded-md text-xs font-mono"
                style={{
                  background: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  color: '#0f172a',
                }}
              />
            </div>
          </div>

          <button
            onClick={handleQuery}
            disabled={!role.trim()}
            className="w-full px-4 py-2 rounded-md text-xs font-semibold transition-opacity"
            style={{
              background: 'rgba(37, 99, 235, 0.15)',
              color: '#2563eb',
              opacity: !role.trim() ? 0.5 : 1,
            }}
          >
            Query Resolution
          </button>
        </div>

        {isLoading && (
          <div className="text-center py-8 text-slate-500">
            Loading...
          </div>
        )}

        {isError && (
          <div className="text-center py-8" style={{ color: '#ef4444' }}>
            Failed to resolve settings
          </div>
        )}

        {data && !isLoading && (
          <div>
            <h3 className="text-xs font-bold mb-3" style={{ color: '#0f172a' }}>
              Effective Settings
            </h3>
            <div className="space-y-2">
              {Object.entries(data.effective).map(([field, value]) => {
                const provenance = data.provenance[field] || 'default';
                return (
                  <div
                    key={field}
                    className="rounded-md border p-3"
                    style={{
                      background: '#f1f5f9',
                      borderColor: '#e2e8f0',
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="text-[10px] font-mono font-semibold mb-1" style={{ color: '#0f172a' }}>
                          {field}
                        </div>
                        <div className="text-xs font-mono text-slate-500">
                          {JSON.stringify(value)}
                        </div>
                      </div>
                      <ProvenanceChip source={provenance} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
