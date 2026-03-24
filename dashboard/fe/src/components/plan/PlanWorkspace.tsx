'use client';

import React, { createContext, useContext, useState } from 'react';
import { usePathname } from 'next/navigation';
import { usePlan } from '@/hooks/use-plans';
import { useEpics } from '@/hooks/use-epics';
import { Plan, Epic, EpicStatus } from '@/types';
import PlanSidebar from './PlanSidebar';
import WorkspaceTabs from './WorkspaceTabs';
import ContextPanel from './ContextPanel';
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
  const { epics, isLoading: epicsLoading, isError: epicsError, updateEpicState } = useEpics(planId);
  
  const [selectedEpicRef, setSelectedEpicRef] = useState<string | null>(null);
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(true);
  // Initialize tab from URL ?tab= param, then manage via React state (SPA — no reloads)
  const [activeTab, setActiveTab] = useState(getInitialTab);

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
        </div>

        {/* Progress Footer */}
        <ProgressFooter />
      </div>
    </PlanContext.Provider>
  );
}
