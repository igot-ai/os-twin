'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useKnowledgeNamespaces } from '@/hooks/use-knowledge-namespaces';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import NamespaceList from '@/components/knowledge/NamespaceList';
import MetricsStrip from '@/components/knowledge/MetricsStrip';

/**
 * Global Knowledge homepage — card grid discovery view.
 *
 * Displays all namespaces in a searchable card grid.
 * Clicking any card navigates to `/knowledge/{name}` which opens
 * the master-detail layout with sidebar + Overview/Import/Query tabs.
 */
export default function KnowledgePage() {
  const router = useRouter();
  const addToast = useNotificationStore((state) => state.addToast);

  const {
    namespaces,
    isLoading,
    createNamespace,
    refresh,
  } = useKnowledgeNamespaces();

  const handleSelectNamespace = useCallback((name: string) => {
    router.push(`/knowledge/${encodeURIComponent(name)}`);
  }, [router]);

  const handleCreateNamespace = useCallback(async (name: string, description?: string, language?: string) => {
    try {
      await createNamespace({ name, description, language });
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
      const { apiDelete } = await import('@/lib/api-client');
      await apiDelete(`/knowledge/namespaces/${name}`);
      refresh();
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
  }, [refresh, addToast]);

  // Loading state
  if (isLoading && !namespaces) {
    return (
      <div className="h-[calc(100vh-56px)] flex items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <div
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }}
          />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Loading knowledge namespaces...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-56px)] overflow-auto bg-background">
      <div className="max-w-[1400px] mx-auto px-6 py-6">
        {/* Page header */}
        <div className="flex items-center gap-3 mb-6">
          <span
            className="material-symbols-outlined text-[28px]"
            style={{ color: 'var(--color-primary)' }}
          >
            auto_stories
          </span>
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-main)' }}>
              Knowledge Base
            </h1>
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Manage namespaces, import documents, and query your knowledge
            </p>
          </div>
        </div>

        {/* Metrics strip */}
        <MetricsStrip className="mb-6" />

        {/* Namespace grid */}
        <NamespaceList
          namespaces={namespaces ?? []}
          selectedNamespace={null}
          onSelect={handleSelectNamespace}
          onCreate={handleCreateNamespace}
          onDelete={handleDeleteNamespace}
          isLoading={isLoading}
          onNamespaceUpdated={refresh}
        />
      </div>
    </div>
  );
}
