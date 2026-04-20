'use client';

import React, { useState, useCallback } from 'react';
import { usePlanContext } from './PlanWorkspace';
import { useKnowledgeNamespaces, NamespaceMetaResponse, useKnowledgeNamespace } from '@/hooks/use-knowledge-namespaces';
import { useKnowledgeImportMonitor } from '@/hooks/use-knowledge-import';
import { useKnowledgeQuery } from '@/hooks/use-knowledge-query';
import { useKnowledgeGraph } from '@/hooks/use-knowledge-graph';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import NamespaceList from './knowledge/NamespaceList';
import ImportPanel from './knowledge/ImportPanel';
import QueryPanel from './knowledge/QueryPanel';
import MetricsStrip from './knowledge/MetricsStrip';

type SubView = 'namespaces' | 'import' | 'query';

// Color palette for label types (matching MemoryTab pattern)
const LABEL_COLORS: Record<string, string> = {
  entity: '#3b82f6',
  person: '#8b5cf6',
  organization: '#ec4899',
  location: '#f97316',
  event: '#10b981',
  concept: '#06b6d4',
  document: '#6366f1',
  default: '#6b7280',
};

export default function KnowledgeTab() {
  const { planId, setActiveTab, setHighlightNoteId } = usePlanContext();
  const [activeSubView, setActiveSubView] = useState<SubView>('namespaces');
  const [selectedNamespace, setSelectedNamespace] = useState<string | null>(null);
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
    graph,
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
      await apiDelete(`/api/knowledge/namespaces/${name}`);
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

  // Handle clicking a memory note from the BacklinkBadge - switch to Memory tab
  const handleNoteClick = useCallback((noteId: string) => {
    // Set the note to highlight in MemoryTab
    setHighlightNoteId(noteId);
    // Switch to the Memory tab
    setActiveTab('memory');
    console.log('Navigate to memory note:', noteId);
  }, [setActiveTab, setHighlightNoteId]);

  // Sub-view tabs
  const subViewTabs: { id: SubView; label: string; icon: string }[] = [
    { id: 'namespaces', label: 'Namespaces', icon: 'folder_open' },
    { id: 'import', label: 'Import', icon: 'upload' },
    { id: 'query', label: 'Query', icon: 'search' },
  ];

  // Loading state
  if (namespacesLoading && !namespaces) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <div 
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} 
          />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading knowledge namespaces...</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (!namespaces || namespaces.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-4 max-w-md">
          <span 
            className="material-symbols-outlined text-[48px]" 
            style={{ color: 'var(--color-text-muted)' }}
          >
            auto_stories
          </span>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-main)' }}>
            No Knowledge Namespaces
          </h3>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Create a namespace to start importing and querying your knowledge base.
          </p>
          <NamespaceList
            namespaces={[]}
            selectedNamespace={selectedNamespace}
            onSelect={handleSelectNamespace}
            onCreate={handleCreateNamespace}
            onDelete={handleDeleteNamespace}
            isLoading={namespacesLoading}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header with sub-view tabs */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center gap-3">
          <span 
            className="material-symbols-outlined text-[20px]" 
            style={{ color: 'var(--color-primary)' }}
          >
            auto_stories
          </span>
          <h2 className="text-base font-semibold" style={{ color: 'var(--color-text-main)' }}>
            Knowledge
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
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        {/* EPIC-005: Metrics panel */}
        <div className="border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <MetricsStrip className="m-2" />
        </div>
        
        <div className="flex-1 overflow-auto">
          {activeSubView === 'namespaces' && (
            <NamespaceList
              namespaces={namespaces}
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
