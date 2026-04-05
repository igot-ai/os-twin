import { IdeaChat } from '@/components/ideas/IdeaChat';

export const dynamicParams = false;

// Only generate one template page for the static export.
// FastAPI serves this same page for ANY /ideas/{id} route (SPA fallback),
// and client-side code reads the real thread ID from the URL.
export async function generateStaticParams() {
  // Required for static export of dynamic routes in Next.js
  // Ensure it matches backend expectations (pt-001 or template)
  return [{ threadId: 'template' }, { threadId: 'pt-001' }];
}

export default async function IdeaThreadPage({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  return <IdeaChat threadId={threadId} />;
}
