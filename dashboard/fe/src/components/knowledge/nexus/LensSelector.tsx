'use client';

import React from 'react';
import type { LensMode } from '@/hooks/use-knowledge-explorer';

interface LensSelectorProps {
  active: LensMode;
  onSet: (lens: LensMode) => void;
}

const LENSES: { id: LensMode; label: string; icon: string }[] = [
  { id: 'structural', label: 'Structural', icon: 'account_tree' },
  { id: 'semantic', label: 'Semantic', icon: 'psychology' },
  { id: 'category', label: 'Category', icon: 'category' },
];

export default function LensSelector({ active, onSet }: LensSelectorProps) {
  return (
    <div className="flex items-center gap-1">
      {LENSES.map(lens => (
        <button
          key={lens.id}
          onClick={() => onSet(lens.id)}
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium border transition-all"
          style={{
            background: active === lens.id ? 'var(--color-primary-muted)' : 'transparent',
            borderColor: active === lens.id ? 'var(--color-primary)' : 'var(--color-border)',
            color: active === lens.id ? 'var(--color-primary)' : 'var(--color-text-muted)',
          }}
        >
          <span className="material-symbols-outlined text-[12px]">{lens.icon}</span>
          {lens.label}
        </button>
      ))}
    </div>
  );
}
