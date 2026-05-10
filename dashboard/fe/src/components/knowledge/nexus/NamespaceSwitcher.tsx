'use client';

import React from 'react';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';

interface NamespaceSwitcherProps {
  namespaces: NamespaceMetaResponse[];
  selected: string | null;
  onSelect: (ns: string) => void;
}

export default function NamespaceSwitcher({ namespaces, selected, onSelect }: NamespaceSwitcherProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>
        hub
      </span>
      <span className="text-xs font-bold tracking-wide" style={{ color: 'var(--color-text-main)' }}>
        NEXUS
      </span>
      <select
        value={selected ?? ''}
        onChange={(e) => onSelect(e.target.value)}
        className="px-2 py-1 rounded-lg border text-[11px] font-medium"
        style={{
          background: 'var(--color-surface)',
          borderColor: 'var(--color-border)',
          color: selected ? 'var(--color-primary)' : 'var(--color-text-muted)',
        }}
      >
        <option value="">Select namespace</option>
        {namespaces.map(ns => (
          <option key={ns.name} value={ns.name}>{ns.name}</option>
        ))}
      </select>
    </div>
  );
}
