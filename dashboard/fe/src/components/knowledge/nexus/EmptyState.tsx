'use client';

import React from 'react';

interface EmptyStateProps {
  onSelectNamespace: () => void;
}

export default function EmptyState({ onSelectNamespace }: EmptyStateProps) {
  return (
    <div className="h-full w-full flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at center, rgba(37, 99, 235, 0.04) 0%, transparent 70%)',
        }}
      />
      <div className="text-center space-y-4 max-w-sm relative z-10">
        <div
          className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center border"
          style={{
            background: 'var(--color-primary-muted)',
            borderColor: 'var(--color-border)',
          }}
        >
          <span className="material-symbols-outlined text-[32px]" style={{ color: 'var(--color-primary)' }}>
            hub
          </span>
        </div>
        <h3 className="text-lg font-bold" style={{ color: 'var(--color-text-main)' }}>
          Nexus Explorer
        </h3>
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Select a namespace to begin exploring your knowledge graph.
          Send a sonar ping to discover connections.
        </p>
        <button
          onClick={onSelectNamespace}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white transition-colors"
          style={{ background: 'var(--color-primary)' }}
        >
          <span className="material-symbols-outlined text-[16px]">explore</span>
          Select Namespace
        </button>
      </div>
    </div>
  );
}
