'use client';

import React, { RefObject } from 'react';
import { useNexusContext } from './NexusContext';
import NamespaceSwitcher from './NamespaceSwitcher';
import LensSelector from './LensSelector';
import SearchBar from './SearchBar';

interface TopRailProps {
  searchInputRef?: RefObject<HTMLInputElement | null>;
}

export default function TopRail({ searchInputRef }: TopRailProps) {
  const ctx = useNexusContext();
  const { namespace, graph, query, actions } = ctx;

  return (
    <div
      className="col-span-3 flex items-center gap-3 px-3 border-b shrink-0 relative z-10"
      style={{
        height: 44,
        background: 'var(--surface-overlay-bg)',
        borderColor: 'var(--color-border)',
        backdropFilter: 'var(--surface-overlay-blur)',
      }}
    >
      <NamespaceSwitcher
        namespaces={namespace.namespaces}
        selected={namespace.selectedNamespace}
        onSelect={namespace.onNamespaceChange}
      />

      <div className="w-px h-5 shrink-0" style={{ background: 'var(--color-border)' }} />

      <div className="flex-1 max-w-[620px]">
        <SearchBar
          isLoading={query.queryLoading}
          hasQuery={!!query.queryResult}
          mode={query.queryMode}
          onModeChange={query.setQueryMode}
          onQuery={actions.query}
          onClear={actions.clearQuery}
          inputRef={searchInputRef}
        />
      </div>

      {graph.isSeeded && (
        <>
          <div className="w-px h-5 shrink-0" style={{ background: 'var(--color-border)' }} />
          <LensSelector active={graph.activeLens} onSet={actions.setLens} />
        </>
      )}
    </div>
  );
}
