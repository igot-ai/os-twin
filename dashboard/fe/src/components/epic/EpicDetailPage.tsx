'use client';

import React from 'react';
import { useEpic } from '@/hooks/use-epics';
import { usePlan } from '@/hooks/use-plans';
import EpicHeader from './EpicHeader';
import TaskChecklistPanel from './TaskChecklistPanel';
import LifecycleVisualizer from './LifecycleVisualizer';
import QAPanel from './QAPanel';
import RoleOverridesPanel from './RoleOverridesPanel';
import ChannelFeed from './ChannelFeed';

interface EpicDetailPageProps {
  planId: string;
  epicRef: string;
}

export default function EpicDetailPage({ planId, epicRef }: EpicDetailPageProps) {
  const { epic, isLoading: epicLoading, isError: epicError } = useEpic(planId, epicRef);
  const { plan, isLoading: planLoading } = usePlan(planId);

  if (epicLoading || planLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p className="text-text-muted font-medium">Loading epic data...</p>
        </div>
      </div>
    );
  }

  if (epicError || !epic) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <span className="material-symbols-outlined text-red-500 text-6xl mb-4">error</span>
        <h1 className="text-2xl font-bold text-text-main mb-2">Epic Not Found</h1>
        <p className="text-text-muted max-w-md">
          The epic with reference <strong>{epicRef}</strong> could not be found in plan <strong>{planId}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] overflow-hidden bg-background-light">
      {/* Sticky Header */}
      <EpicHeader plan={plan} epic={epic} />

      {/* Main Content Areas */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Three Panel Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar: Task Checklist */}
          <TaskChecklistPanel planId={planId} epicRef={epicRef} tasks={epic.tasks || []} />

          {/* Center Panel: Lifecycle Visualizer */}
          <section className="flex-1 flex flex-col bg-background-light overflow-hidden">
             <LifecycleVisualizer epic={epic} />
          </section>

          {/* Right Sidebar: QA & Role Overrides */}
          <aside className="w-80 border-l border-border-color bg-surface flex flex-col shrink-0 overflow-hidden">
            {/* Top Half: QA */}
            <div className="h-1/2 flex flex-col border-b border-border-color overflow-hidden">
              <QAPanel definitionOfDone={epic.definition_of_done || []} acceptanceCriteria={epic.acceptance_criteria || []} />
            </div>

            {/* Bottom Half: Role Overrides */}
            <div className="flex-1 flex flex-col overflow-hidden">
               <RoleOverridesPanel epic={epic} />
            </div>
          </aside>
        </div>

        {/* Footer: Channel Feed */}
        <ChannelFeed epic={epic} />
      </main>
    </div>
  );
}
