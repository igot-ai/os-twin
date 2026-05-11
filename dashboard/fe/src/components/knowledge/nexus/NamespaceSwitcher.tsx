'use client';

import React from 'react';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';
import { FONT } from './typography';
import { Icon } from './Icon';

interface NamespaceSwitcherProps {
  namespaces: NamespaceMetaResponse[];
  selected: string | null;
  onSelect: (ns: string) => void;
}

export default function NamespaceSwitcher({ namespaces, selected, onSelect }: NamespaceSwitcherProps) {
  return (
    <div className="flex items-center gap-2">
      <Icon name="hub" size={16} style={{ color: 'var(--color-primary)' }} />
      <select
        value={selected ?? ''}
        onChange={(e) => onSelect(e.target.value)}
        className={`px-2 py-1 rounded-lg border ${FONT.body} font-medium`}
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
