'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import KnowledgeTabCore from '@/components/knowledge/KnowledgeTabCore';

/**
 * Inner component that uses useSearchParams - must be wrapped in Suspense
 */
function KnowledgePageContent() {
  const searchParams = useSearchParams();
  const [defaultNamespace, setDefaultNamespace] = useState<string | undefined>(undefined);
  
  // Read ?ns=xxx query param for deep-linking from plan context
  useEffect(() => {
    const nsParam = searchParams.get('ns');
    if (nsParam) {
      // Decode the namespace name
      setDefaultNamespace(decodeURIComponent(nsParam));
    }
  }, [searchParams]);
  
  return (
    <>
      {/* Page Header */}
      <div className="px-6 py-4 border-b border-border bg-surface shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span 
              className="material-symbols-outlined text-[24px]" 
              style={{ color: 'var(--color-primary)' }}
            >
              auto_stories
            </span>
            <div>
              <h1 className="text-lg font-bold text-text-main">Knowledge Base</h1>
              <p className="text-xs text-text-muted">
                Manage namespaces, import documents, and query your knowledge
              </p>
            </div>
          </div>
          
          {/* Show pre-selected namespace indicator if deep-linked */}
          {defaultNamespace && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10">
              <span className="material-symbols-outlined text-[16px] text-primary">folder_open</span>
              <span className="text-xs font-medium text-primary">
                Pre-selected: {defaultNamespace}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Knowledge Content */}
      <div className="flex-1 overflow-hidden">
        <KnowledgeTabCore
          headerVariant="minimal"
          className="h-full"
          defaultNamespace={defaultNamespace}
        />
      </div>
    </>
  );
}

/**
 * Global Knowledge page - standalone knowledge management interface.
 * This page provides access to knowledge namespaces, import, and query
 * functionality outside of a plan context.
 * 
 * Unlike PlanKnowledgeTab, this page does not integrate with plan-specific
 * features like Memory tab navigation or note highlighting.
 * 
 * Supports deep-linking via ?ns=xxx query parameter to pre-select a namespace.
 */
export default function KnowledgePage() {
  return (
    <div className="h-[calc(100vh-56px)] flex flex-col bg-background">
      <Suspense fallback={
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <div 
              className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
              style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} 
            />
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Loading knowledge...
            </p>
          </div>
        </div>
      }>
        <KnowledgePageContent />
      </Suspense>
    </div>
  );
}
