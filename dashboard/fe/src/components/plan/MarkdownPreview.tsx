'use client';

import { useContext } from 'react';
import { PlanContext } from './PlanWorkspace';
import { StructuredPlanView } from './StructuredPlanView';
import { MarkdownRenderer } from '@/lib/markdown-renderer';

interface MarkdownPreviewProps {
  content: string;
}

export function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const context = useContext(PlanContext);
  const parsedPlan = context?.parsedPlan;

  // If we have a successfully parsed plan, use the structured view
  if (parsedPlan && parsedPlan.epics.length > 0) {
    return <StructuredPlanView />;
  }

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar">
      {content.trim() ? (
        <MarkdownRenderer content={content} />
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">visibility</span>
          <p className="text-sm text-text-muted">Nothing to preview yet.</p>
        </div>
      )}
    </div>
  );
}
