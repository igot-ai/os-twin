'use client';

import React, { Suspense, lazy } from 'react';
import { usePlanContext } from './PlanWorkspace';

// Lazy-load tab components
const KanbanBoard = lazy(() => import('./KanbanBoard'));
const RolesTab = lazy(() => import('./placeholder/RolesTab'));
const SkillsTab = lazy(() => import('./placeholder/SkillsTab'));
const DAGTab = lazy(() => import('./placeholder/DAGTab'));
const SettingsTab = lazy(() => import('./placeholder/SettingsTab'));
const PlanEditorTab = lazy(() => import('./PlanEditorTab'));
const PlanPreviewTab = lazy(() => import('./PlanPreviewTab'));
const PlanSettingsTab = lazy(() => import('./PlanSettingsTab'));
const PlanHistoryTab = lazy(() => import('./PlanHistoryTab'));

export default function WorkspaceTabs() {
  const { activeTab, planId, planContent, setPlanContent } = usePlanContext();

  const renderContent = () => {
    switch (activeTab) {
      case 'epics':
        return <KanbanBoard />;
      case 'roles':
        return <RolesTab />;
      case 'skills':
        return <SkillsTab />;
      case 'dag':
        return <DAGTab />;
      case 'settings':
        return <SettingsTab />;
      case 'editor':
        return <PlanEditorTab content={planContent} onChange={setPlanContent} />;
      case 'preview':
        return <PlanPreviewTab content={planContent} />;
      case 'plan-settings':
        return <PlanSettingsTab planId={planId} />;
      case 'history':
        return <PlanHistoryTab planId={planId} />;
      default:
        return <KanbanBoard />;
    }
  };

  return (
    <div className="flex-1 h-full overflow-hidden">
      <Suspense fallback={
        <div className="p-10 animate-pulse flex flex-col gap-6">
          <div className="h-10 w-64 bg-border/20 rounded-lg" />
          <div className="grid grid-cols-4 gap-4 h-full">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-[500px] bg-border/10 rounded-2xl" />
            ))}
          </div>
        </div>
      }>
        {renderContent()}
      </Suspense>
    </div>
  );
}
