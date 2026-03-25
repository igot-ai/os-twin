'use client';

import React, { createContext, useContext, useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { usePlan } from '@/hooks/use-plans';
import { useEpics, useDAG } from '@/hooks/use-epics';
import { useWarRoomProgress } from '@/hooks/use-war-room';
import { usePlanRefine } from '@/hooks/use-plan-refine';
import { apiPost } from '@/lib/api-client';
import { Plan, Epic, EpicStatus } from '@/types';
import PlanSidebar from './PlanSidebar';
import WorkspaceTabs from './WorkspaceTabs';
import ContextPanel from './ContextPanel';
import AIChatPanel from './AIChatPanel';
import PlanBreadcrumb from './PlanBreadcrumb';
import ProgressFooter from './ProgressFooter';

interface PlanContextType {
  planId: string;
  plan: Plan | undefined;
  epics: Epic[] | undefined;
  isLoading: boolean;
  isError: unknown;
  selectedEpicRef: string | null;
  setSelectedEpicRef: (ref: string | null) => void;
  updateEpicState: (ref: string, lifecycle_state: string, status: EpicStatus) => Promise<Epic | undefined>;
  isContextPanelOpen: boolean;
  setIsContextPanelOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  planContent: string;
  setPlanContent: (content: string) => void;
  savePlan: () => Promise<void>;
  launchPlan: () => Promise<void>;
  isSaving: boolean;
  isAIChatOpen: boolean;
  setIsAIChatOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
}

const PlanContext = createContext<PlanContextType | undefined>(undefined);

export function usePlanContext() {
  const context = useContext(PlanContext);
  if (!context) {
    throw new Error('usePlanContext must be used within a PlanProvider');
  }
  return context;
}

// Read initial tab from URL query string client-side (avoids useSearchParams Suspense issue)
function getInitialTab(): string {
  if (typeof window === 'undefined') return 'epics';
  const params = new URLSearchParams(window.location.search);
  return params.get('tab') || 'epics';
}

export default function PlanWorkspace({ planId: propId }: { planId: string }) {
  // In static export mode, the prop contains the template's baked ID (e.g. "plan-001").
  // usePathname() reads the actual browser URL so we can extract the real plan ID.
  const pathname = usePathname();
  const pathSegments = pathname?.split('/').filter(Boolean);
  // URL format: /plans/{id} → pathSegments = ['plans', '{id}']
  const planId = (pathSegments?.[0] === 'plans' && pathSegments?.[1]) ? pathSegments[1] : propId;

  const { plan, isLoading: planLoading, isError: planError } = usePlan(planId);
  const { epics: apiEpics, isLoading: epicsLoading, isError: epicsError, updateEpicState } = useEpics(planId);
  const { dag } = useDAG(planId);
  const { progress } = useWarRoomProgress(planId);
  
  const [selectedEpicRef, setSelectedEpicRef] = useState<string | null>(null);
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(true);
  const [isAIChatOpen, setIsAIChatOpen] = useState(false);
  // Initialize tab from URL ?tab= param, then manage via React state (SPA — no reloads)
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [planContent, setPlanContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const {
    chatHistory,
    isRefining,
    streamedResponse,
    error: aiError,
    refine,
    cancelRefine,
    clearHistory,
  } = usePlanRefine();

  useEffect(() => {
    if (plan?.content !== undefined && planContent === '') {
      setPlanContent(plan.content);
    }
  }, [plan?.content]);  // eslint-disable-line react-hooks/exhaustive-deps

  const savePlan = useCallback(async () => {
    setIsSaving(true);
    try {
      await apiPost(`/plans/${planId}/save`, { content: planContent });
    } finally {
      setIsSaving(false);
    }
  }, [planId, planContent]);

  const launchPlan = useCallback(async () => {
    await savePlan();
    await apiPost('/run', { plan: planContent, plan_id: planId });
  }, [savePlan, planContent, planId]);

  const handleApplyAI = useCallback((newContent: string) => {
    setPlanContent(newContent);
    setActiveTab('editor');
  }, []);

  // Synthesize epics from progress + DAG when the /epics API returns empty
  const epics = useMemo(() => {
    if (apiEpics && apiEpics.length > 0) return apiEpics;
    if (!progress?.rooms || !dag?.nodes) return apiEpics;

    return progress.rooms.map((room): Epic => {
      const dagNode = dag.nodes[room.task_ref];
      return {
        epic_ref: room.task_ref,
        plan_id: planId,
        title: room.task_ref,
        lifecycle_state: room.status,
        status: room.status as EpicStatus,
        role: dagNode?.role || 'unknown',
        room_id: room.room_id,
        depends_on: dagNode ? (Array.isArray(dagNode.depends_on) ? dagNode.depends_on : dagNode.depends_on ? [dagNode.depends_on] : []) : [],
        dependents: dagNode?.dependents || [],
        tasks: [],
      };
    });
  }, [apiEpics, progress, dag, planId]);

  const contextValue: PlanContextType = {
    planId,
    plan,
    epics,
    isLoading: planLoading || epicsLoading,
    isError: planError || epicsError,
    selectedEpicRef,
    setSelectedEpicRef,
    updateEpicState,
    isContextPanelOpen,
    setIsContextPanelOpen,
    activeTab,
    setActiveTab,
    planContent,
    setPlanContent,
    savePlan,
    launchPlan,
    isSaving,
    isAIChatOpen,
    setIsAIChatOpen,
  };

  if (planLoading && !plan) {
    return <div className="p-8 animate-pulse">Loading plan...</div>;
  }

  if (planError) {
    return (
      <div className="p-8 flex flex-col items-center justify-center h-full">
        <span className="material-symbols-outlined text-danger text-4xl mb-2">error</span>
        <h2 className="text-xl font-bold text-text-main">Failed to load plan</h2>
        <p className="text-text-muted mt-2">The requested plan could not be found or there was a server error.</p>
      </div>
    );
  }

  return (
    <PlanContext.Provider value={contextValue}>
      <div className="flex flex-col h-[calc(100vh-56px)] bg-background">
        {/* Breadcrumb Header */}
        <div className="px-6 py-2 border-b bg-surface border-border shrink-0">
          <PlanBreadcrumb />
        </div>

        {/* Three Panel Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel: Sidebar (Metadata + Tab Nav) */}
          <aside className="w-[240px] border-r bg-surface border-border flex flex-col shrink-0">
            <PlanSidebar />
          </aside>

          {/* Center Panel: Content Area */}
          <main className="flex-1 flex flex-col overflow-hidden bg-background">
            <WorkspaceTabs />
          </main>

          {/* Right Panel: Contextual Panel */}
          <aside
            className={`border-l bg-surface border-border flex flex-col shrink-0 transition-all duration-300 overflow-hidden ${
              isContextPanelOpen ? 'w-[360px]' : 'w-0 border-l-0'
            }`}
          >
            <div className="w-[360px] h-full">
              <ContextPanel />
            </div>
          </aside>

          {/* Right Panel: AI Chat */}
          <aside
            className={`border-l bg-surface border-border flex flex-col shrink-0 transition-all duration-300 overflow-hidden ${
              isAIChatOpen ? 'w-[360px]' : 'w-0 border-l-0'
            }`}
          >
            <div className="w-[360px] h-full">
              <AIChatPanel
                chatHistory={chatHistory}
                isRefining={isRefining}
                streamedResponse={streamedResponse}
                error={aiError}
                onSendMessage={(msg) => refine(msg, planContent, planId)}
                onApplyToEditor={handleApplyAI}
                onCancel={cancelRefine}
                onClearHistory={() => { clearHistory(); setIsAIChatOpen(false); }}
              />
            </div>
          </aside>
        </div>

        {/* Progress Footer */}
        <ProgressFooter />
      </div>
    </PlanContext.Provider>
  );
}
