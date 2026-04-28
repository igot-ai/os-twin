'use client';

import { useParams, useSearchParams } from 'next/navigation';
import KnowledgeTabCore from '@/components/knowledge/KnowledgeTabCore';

/**
 * Client component that reads route params and renders the detail view.
 */
export default function NamespaceDetailContent() {
  const params = useParams();
  const searchParams = useSearchParams();

  // Extract the namespace name from the route
  const namespaceName = typeof params.name === 'string'
    ? decodeURIComponent(params.name)
    : Array.isArray(params.name)
      ? decodeURIComponent(params.name[0])
      : '';

  // Optional tab query param: /knowledge/my-ns?tab=import
  const tabParam = searchParams.get('tab');
  const defaultTab = tabParam === 'import' || tabParam === 'query' ? tabParam : undefined;

  if (!namespaceName) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <span
            className="material-symbols-outlined text-[48px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            error
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            Invalid Namespace
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            No namespace name was provided in the URL.
          </p>
        </div>
      </div>
    );
  }

  return (
    <KnowledgeTabCore
      headerVariant="minimal"
      className="h-full"
      defaultNamespace={namespaceName}
      defaultTab={defaultTab}
    />
  );
}
