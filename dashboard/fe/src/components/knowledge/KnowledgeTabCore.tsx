'use client';

import React, { useState, useCallback } from 'react';
import { useKnowledgeNamespaces } from '@/hooks/use-knowledge-namespaces';
import { useKnowledgeImportMonitor } from '@/hooks/use-knowledge-import';
import { useKnowledgeQuery } from '@/hooks/use-knowledge-query';
import { useKnowledgeGraph } from '@/hooks/use-knowledge-graph';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import NamespaceList from '@/components/knowledge/NamespaceList';
import ImportPanel from '@/components/knowledge/ImportPanel';
import QueryPanel from '@/components/knowledge/QueryPanel';
import MetricsStrip from '@/components/knowledge/MetricsStrip';

type SubView = 'namespaces' | 'import' | 'query';

/**
 * Props interface for the KnowledgeTabCore component.
 * This component is decoupled from PlanContext and can be used in both
 * plan and global contexts.
 */
export interface KnowledgeTabCoreProps {
  /** Optional callback when a note is clicked (e.g., to navigate to Memory tab) */
  onNoteClick?: (noteId: string) => void;
  /** Optional default namespace to select on mount */
  defaultNamespace?: string;
  /** Optional header variant - 'full' shows title with icon, 'minimal' hides header */
  headerVariant?: 'full' | 'minimal';
  /** Optional CSS class name for the container */
  className?: string;
  /** Whether this is being used in a plan context (changes header text) */
  isPlanContext?: boolean;
  /** Callback for "View All Knowledge" navigation (plan context only) */
  onViewAllKnowledge?: () => void;
  /** Whether to show the MetricsStrip panel (default: true) */
  showMetrics?: boolean;
  /** If set, filter namespaces to only show this specific namespace */
  filterNamespace?: string;
}

/**
 * Core KnowledgeTab component that is decoupled from PlanContext.
 * All plan-specific behaviors are passed via optional props.
 * 
 * Usage:
 * - In plan context: Use PlanKnowledgeTab wrapper which bridges PlanContext
 * - In global context: Use directly with no plan-specific props
 */
export default function KnowledgeTabCore({
  onNoteClick,
  defaultNamespace,
  headerVariant = 'full',
  className = '',
  isPlanContext = false,
  onViewAllKnowledge,
  showMetrics = true,
  filterNamespace,
}: KnowledgeTabCoreProps) {
  // In plan context with a filter, default to 'query' since there's only one namespace
  const [activeSubView, setActiveSubView] = useState<SubView>(isPlanContext && filterNamespace ? 'query' : 'namespaces');
  const [selectedNamespace, setSelectedNamespace] = useState<string | null>(defaultNamespace ?? filterNamespace ?? null);
  const addToast = useNotificationStore((state) => state.addToast);

  // Hooks
  const {
    namespaces,
    isLoading: namespacesLoading,
    createNamespace,
    refresh: refreshNamespaces,
  } = useKnowledgeNamespaces();

  const {
    jobs,
    activeJob,
    isLoading: jobsLoading,
    startImport,
    refreshJobs,
  } = useKnowledgeImportMonitor(selectedNamespace);

  const {
    result: queryResult,
    isLoading: queryLoading,
    error: queryError,
    executeQuery,
    clearResult,
  } = useKnowledgeQuery(selectedNamespace);

  const {
    nodes,
    edges,
    stats: graphStats,
    isLoading: graphLoading,
    refresh: refreshGraph,
  } = useKnowledgeGraph(selectedNamespace);

  // Handlers
  const handleSelectNamespace = useCallback((ns: string) => {
    setSelectedNamespace(ns);
    setActiveSubView('query'); // Switch to query view when namespace selected
  }, []);

  const handleCreateNamespace = useCallback(async (name: string, description?: string) => {
    try {
      await createNamespace({ name, description });
      addToast({
        type: 'success',
        title: 'Namespace Created',
        message: `Namespace "${name}" has been created successfully.`,
        autoDismiss: true,
      });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create namespace';
      addToast({
        type: 'error',
        title: 'Creation Failed',
        message: errorMessage,
        autoDismiss: false,
      });
    }
  }, [createNamespace, addToast]);

  const handleDeleteNamespace = useCallback(async (name: string) => {
    try {
      // Use the hook's deleteNamespace method via a direct API call
      const { apiDelete } = await import('@/lib/api-client');
      await apiDelete(`/knowledge/namespaces/${name}`);
      refreshNamespaces();
      addToast({
        type: 'success',
        title: 'Namespace Deleted',
        message: `Namespace "${name}" has been deleted successfully.`,
        autoDismiss: true,
      });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete namespace';
      addToast({
        type: 'error',
        title: 'Deletion Failed',
        message: errorMessage,
        autoDismiss: false,
      });
    }
  }, [refreshNamespaces, addToast]);

  const handleStartImport = useCallback(async (folderPath: string, options?: Record<string, unknown>) => {
    if (!selectedNamespace) {
      addToast({
        type: 'error',
        title: 'No Namespace Selected',
        message: 'Please select a namespace before importing.',
        autoDismiss: false,
      });
      return;
    }

    try {
      await startImport(selectedNamespace, { folder_path: folderPath, options });
      refreshJobs();
      addToast({
        type: 'success',
        title: 'Import Started',
        message: `Import job has been started for "${folderPath}".`,
        autoDismiss: true,
      });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start import';
      addToast({
        type: 'error',
        title: 'Import Failed',
        message: errorMessage,
        autoDismiss: false,
      });
    }
  }, [selectedNamespace, startImport, refreshJobs, addToast]);

  const handleExecuteQuery = useCallback(async (query: string, mode: 'raw' | 'graph' | 'summarized', topK: number) => {
    try {
      await executeQuery({ query, mode, top_k: topK });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Query failed';
      addToast({
        type: 'error',
        title: 'Query Failed',
        message: errorMessage,
        autoDismiss: false,
      });
    }
  }, [executeQuery, addToast]);

  // Handle clicking a memory note from the BacklinkBadge
  // In plan context, this switches to Memory tab and highlights the note
  // In global context, this is a no-op (or could navigate to a note detail page)
  const handleNoteClick = useCallback((noteId: string) => {
    if (onNoteClick) {
      onNoteClick(noteId);
    }
  }, [onNoteClick]);

  // Filter namespaces when filterNamespace is set (plan context)
  const displayNamespaces = filterNamespace
    ? (namespaces ?? []).filter(ns => ns.name === filterNamespace)
    : namespaces;

  // Sub-view tabs — hide Namespaces tab when filtering to a single namespace
  const subViewTabs: { id: SubView; label: string; icon: string }[] = [
    ...(filterNamespace ? [] : [{ id: 'namespaces' as SubView, label: 'Namespaces', icon: 'grid_view' }]),
    { id: 'import', label: 'Import', icon: 'upload' },
    { id: 'query', label: 'Query', icon: 'search' },
  ];

  // Loading state
  if (namespacesLoading && !namespaces) {
    return (
      <div className={`h-full flex items-center justify-center ${className}`}>
        <div className="text-center space-y-3">
          <div 
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} 
          />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            {isPlanContext ? 'Loading plan knowledge...' : 'Loading knowledge namespaces...'}
          </p>
        </div>
      </div>
    );
  }

  // Empty state — use displayNamespaces for filtered view
  if (!namespaces || namespaces.length === 0 || (filterNamespace && displayNamespaces?.length === 0)) {
    return (
      <div className={`h-full flex items-center justify-center ${className}`}>
        <div className="text-center space-y-4 max-w-md">
          <span 
            className="material-symbols-outlined text-[48px]" 
            style={{ color: 'var(--color-text-muted)' }}
          >
            auto_stories
          </span>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-main)' }}>
            {filterNamespace ? 'Plan Namespace Not Ready' : 'No Knowledge Namespaces'}
          </h3>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            {filterNamespace
              ? `The namespace "${filterNamespace}" is being set up for this plan.`
              : 'Create a namespace to start importing and querying your knowledge base.'}
          </p>
          {!filterNamespace && (
            <NamespaceList
              namespaces={[]}
              selectedNamespace={selectedNamespace}
              onSelect={handleSelectNamespace}
              onCreate={handleCreateNamespace}
              onDelete={handleDeleteNamespace}
              isLoading={namespacesLoading}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`h-full flex flex-col overflow-hidden ${className}`}>
      {/* Header with sub-view tabs */}
      {headerVariant === 'full' && (
        <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center gap-3">
            <span 
              className="material-symbols-outlined text-[20px]" 
              style={{ color: 'var(--color-primary)' }}
            >
              auto_stories
            </span>
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
              {isPlanContext ? 'Plan Knowledge' : 'Knowledge'}
            </h2>
            {selectedNamespace && (
              <span 
                className="px-2 py-0.5 rounded-md text-[11px] font-medium"
                style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
              >
                {selectedNamespace}
              </span>
            )}
          </div>

          {/* Right side: Sub-view tabs + View All Knowledge link (plan context) */}
          <div className="flex items-center gap-2">
            {/* Sub-view tabs */}
            <nav className="flex items-center gap-1">
              {subViewTabs.map((tab) => {
                const isActive = activeSubView === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveSubView(tab.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                      isActive 
                        ? 'bg-primary/10 text-primary' 
                        : 'text-text-muted hover:bg-surface-hover hover:text-text-main'
                    }`}
                    aria-label={tab.label}
                  >
                    <span className="material-symbols-outlined text-[16px]">
                      {tab.icon}
                    </span>
                    {tab.label}
                  </button>
                );
              })}
            </nav>
            
            {/* View All Knowledge link (plan context only) */}
            {isPlanContext && onViewAllKnowledge && (
              <button
                onClick={onViewAllKnowledge}
                className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-primary hover:bg-primary/10 transition-all"
                aria-label="View all knowledge in global page"
              >
                <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                View All Knowledge
              </button>
            )}
          </div>
        </div>
      )}

      {/* Minimal header — just tabs for the global page */}
      {headerVariant === 'minimal' && (
        <div 
          className="flex items-center gap-1 px-5 pt-3 pb-0 shrink-0"
        >
          <nav className="flex items-center gap-1">
            {subViewTabs.map((tab) => {
              const isActive = activeSubView === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveSubView(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive 
                      ? 'bg-primary/10 text-primary' 
                      : 'text-text-muted hover:bg-surface-hover hover:text-text-main'
                  }`}
                  aria-label={tab.label}
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {tab.icon}
                  </span>
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* Selected namespace badge */}
          {selectedNamespace && activeSubView !== 'namespaces' && (
            <div className="flex items-center gap-2 ml-auto">
              <span 
                className="px-2.5 py-1 rounded-lg text-[11px] font-semibold flex items-center gap-1.5"
                style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>folder_open</span>
                {selectedNamespace}
              </span>
              <button
                onClick={() => { setSelectedNamespace(null); setActiveSubView('namespaces'); }}
                className="text-[10px] font-medium px-2 py-1 rounded-md hover:bg-surface-hover transition-colors"
                style={{ color: 'var(--color-text-faint)' }}
              >
                Change
              </button>
            </div>
          )}
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* Metrics panel — hidden in plan context */}
        {showMetrics && activeSubView === 'namespaces' && (
          <div className="border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
            <MetricsStrip className="m-2" />
          </div>
        )}
        
        <div className="flex-1 overflow-auto">
          {activeSubView === 'namespaces' && (
            <NamespaceList
              namespaces={displayNamespaces ?? []}
              selectedNamespace={selectedNamespace}
              onSelect={handleSelectNamespace}
              onCreate={handleCreateNamespace}
              onDelete={handleDeleteNamespace}
              isLoading={namespacesLoading}
              onNamespaceUpdated={refreshNamespaces}
            />
          )}

          {activeSubView === 'import' && (
            <ImportPanel
              selectedNamespace={selectedNamespace}
              jobs={jobs ?? []}
              activeJob={activeJob}
              isLoading={jobsLoading}
              onStartImport={handleStartImport}
              onRefresh={refreshJobs}
            />
          )}

          {activeSubView === 'query' && (
            <QueryPanel
              selectedNamespace={selectedNamespace}
              queryResult={queryResult}
              isLoading={queryLoading}
              error={queryError}
              graphNodes={nodes}
              graphEdges={edges}
              graphStats={graphStats}
              graphLoading={graphLoading}
              onExecuteQuery={handleExecuteQuery}
              onClearResult={clearResult}
              onRefreshGraph={refreshGraph}
              onNoteClick={handleNoteClick}
            />
          )}
        </div>
      </div>
    </div>
  );
}
