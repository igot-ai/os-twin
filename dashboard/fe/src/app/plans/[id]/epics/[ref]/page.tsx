import React from "react";
import EpicDetail from "@/components/epic/EpicDetailPage";

// Only generate one template page for the static export.
// FastAPI serves this same page for ANY /plans/{id}/epics/{ref} route (SPA fallback),
// and client-side code reads the real IDs from the URL.
export function generateStaticParams() {
  return [{ id: "plan-001", ref: "EPIC-001" }];
}

export default async function EpicPage({
  params,
}: {
  params: Promise<{ id: string; ref: string }>;
}) {
  const { id, ref } = await params;

  return <EpicDetail planId={id} epicRef={ref} />;
}
