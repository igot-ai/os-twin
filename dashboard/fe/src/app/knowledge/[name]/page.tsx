import { Suspense } from 'react';
import NamespaceDetailContent from './NamespaceDetailContent';

/**
 * Required for Next.js `output: 'export'` in production builds.
 * Generates a single template page — the actual namespace is resolved
 * client-side via useParams(). FastAPI serves this page for any /knowledge/{name} route.
 */
export function generateStaticParams() {
  return [{ name: '_' }];
}

/**
 * Dynamic route for namespace detail: /knowledge/[name]
 *
 * Provides a shareable URL that deep-links directly into a specific
 * namespace's master-detail view with sidebar + Overview/Import/Query tabs.
 *
 * Examples:
 *   /knowledge/vnexpress_global_news          → Overview tab
 *   /knowledge/vnexpress_global_news?tab=import → Import tab
 *   /knowledge/vnexpress_global_news?tab=query  → Query tab
 */
export default function NamespaceDetailPage() {
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
              Loading namespace...
            </p>
          </div>
        </div>
      }>
        <NamespaceDetailContent />
      </Suspense>
    </div>
  );
}
