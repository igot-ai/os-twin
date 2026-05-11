'use client';

import React from 'react';
import type { LensMode } from '@/hooks/use-knowledge-explorer';
import { FONT } from './typography';
import { Icon } from './Icon';

interface LensSelectorProps {
  active: LensMode;
  onSet: (lens: LensMode) => void;
}

const LENSES: { id: LensMode; label: string; icon: string }[] = [
  { id: 'structural', label: 'Structural', icon: 'account_tree' },
  { id: 'semantic', label: 'Semantic', icon: 'psychology' },
  { id: 'category', label: 'Category', icon: 'category' },
  { id: 'community', label: 'Community', icon: 'hub' },
];

export default function LensSelector({ active, onSet }: LensSelectorProps) {
  return (
    <div className="flex items-center gap-1">
      {LENSES.map(lens => (
        <button
          key={lens.id}
          onClick={() => onSet(lens.id)}
          className={`flex items-center gap-1 px-2 py-1 rounded-lg ${FONT.label} font-medium border transition-all`}
          style={{
            background: active === lens.id ? 'var(--color-primary-muted)' : 'transparent',
            borderColor: active === lens.id ? 'var(--color-primary)' : 'var(--color-border)',
            color: active === lens.id ? 'var(--color-primary)' : 'var(--color-text-muted)',
          }}
        >
          <Icon name={lens.icon} size={12} />
          {lens.label}
        </button>
      ))}
    </div>
  );
}
