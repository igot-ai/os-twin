import React from 'react';
import PlanWorkspace from '@/components/plan/PlanWorkspace';

// Only generate one template page for the static export.
// FastAPI serves this same page for ANY /plans/{id} route (SPA fallback),
// and client-side code reads the real plan ID from the URL.
export function generateStaticParams() {
  return [{ id: 'plan-001' }];
}

export default async function PlanWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return <PlanWorkspace planId={id} />;
}
