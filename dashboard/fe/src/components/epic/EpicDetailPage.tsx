'use client';

import React, { useState } from 'react';
import { useEpic } from '@/hooks/use-epics';
import { usePlan } from '@/hooks/use-plans';
import { useAgentInstances } from '@/hooks/use-war-room';
import EpicHeader from './EpicHeader';
import TaskChecklistPanel from './TaskChecklistPanel';
import LifecycleVisualizer from './LifecycleVisualizer';
import QAPanel from './QAPanel';
import RoleOverridesPanel from './RoleOverridesPanel';
import ChannelFeed from './ChannelFeed';
import BriefPanel from './BriefPanel';
import AuditTimeline from './AuditTimeline';
import AgentInstanceCard from './AgentInstanceCard';
import ArtifactsViewer from './ArtifactsViewer';

interface EpicDetailPageProps {
  planId: string;
  epicRef: string;
}

type RightTab = 'qa' | 'brief' | 'audit' | 'agents' | 'artifacts';

export default function EpicDetailPage({ planId, epicRef }: EpicDetailPageProps) {
  const { epic, isLoading: epicLoading, isError: epicError } = useEpic(planId, epicRef);
  const { plan, isLoading: planLoading } = usePlan(planId);
  const { agents } = useAgentInstances(planId, epicRef);
  const [rightTab, setRightTab] = useState<RightTab>('qa');

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

  const rightTabs: { id: RightTab; label: string; icon: string }[] = [
    { id: 'qa', label: 'QA', icon: 'verified' },
    { id: 'brief', label: 'Brief', icon: 'description' },
    { id: 'audit', label: 'Audit', icon: 'history' },
    { id: 'agents', label: 'Agents', icon: 'smart_toy' },
    { id: 'artifacts', label: 'Files', icon: 'folder_special' },
  ];

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

          {/* Right Sidebar: Tabbed War Room Panels */}
          <aside className="w-80 border-l border-border-color bg-surface flex flex-col shrink-0 overflow-hidden">
            {/* Tab Navigation */}
            <div className="flex border-b border-border shrink-0 overflow-x-auto custom-scrollbar">
              {rightTabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setRightTab(tab.id)}
                  className={`flex items-center gap-1 px-3 py-2 text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap border-b-2 ${
                    rightTab === tab.id
                      ? 'border-primary text-primary bg-primary/5'
                      : 'border-transparent text-text-faint hover:text-text-muted hover:bg-surface-hover'
                  }`}
                >
                  <span className="material-symbols-outlined text-[14px]">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-hidden">
              {rightTab === 'qa' && (
                <div className="flex flex-col h-full overflow-hidden">
                  {/* QA Panel */}
                  <div className="h-1/2 flex flex-col border-b border-border-color overflow-hidden">
                    <QAPanel definitionOfDone={epic.definition_of_done || []} acceptanceCriteria={epic.acceptance_criteria || []} />
                  </div>
                  {/* Role Overrides */}
                  <div className="flex-1 flex flex-col overflow-hidden">
                    <RoleOverridesPanel epic={epic} />
                  </div>
                </div>
              )}
              {rightTab === 'brief' && (
                <BriefPanel planId={planId} epicRef={epicRef} />
              )}
              {rightTab === 'audit' && (
                <AuditTimeline planId={planId} epicRef={epicRef} />
              )}
              {rightTab === 'agents' && (
                <div className="flex flex-col h-full overflow-hidden">
                  <div className="px-4 py-3 border-b border-border bg-surface-hover/30 flex items-center justify-between shrink-0">
                    <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
                      <span className="material-symbols-outlined text-sm">smart_toy</span>
                      Agent Instances
                    </h3>
                    <span className="text-[10px] font-mono text-text-faint bg-surface-hover px-1.5 py-0.5 rounded">
                      {agents?.length || 0}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
                    {agents && agents.length > 0 ? (
                      agents.map(agent => (
                        <AgentInstanceCard key={agent.instance_id} agent={agent} />
                      ))
                    ) : (
                      <div className="p-4 text-center text-text-faint">
                        <span className="material-symbols-outlined text-2xl mb-2 block">smart_toy</span>
                        <p className="text-xs">No agent instances found.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {rightTab === 'artifacts' && (
                <ArtifactsViewer planId={planId} epicRef={epicRef} />
              )}
            </div>
          </aside>
        </div>

        {/* Footer: Channel Feed */}
        <ChannelFeed epic={epic} />
      </main>
    </div>
  );
}
