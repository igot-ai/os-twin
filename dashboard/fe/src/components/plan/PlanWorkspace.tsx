'use client';

import React, { createContext, useContext, useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { usePlan } from '@/hooks/use-plans';
import { useEpics, useDAG } from '@/hooks/use-epics';
import { useWarRoomProgress } from '@/hooks/use-war-room';
import { usePlanRefine } from '@/hooks/use-plan-refine';
import { apiPost } from '@/lib/api-client';
import { useNotificationStore } from '@/lib/stores/notificationStore';
import { Plan, Epic, EpicStatus, WarRoomProgress } from '@/types';
import { parseEpicMarkdown, serializeEpicMarkdown, EpicDocument } from '@/lib/epic-parser';
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
  progress: WarRoomProgress | undefined;
  isLoading: boolean;
  isProgressLoading: boolean;
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
  reloadFromDisk: () => Promise<void>;
  syncStatus: { in_sync: boolean; disk_mtime: number; zvec_mtime: number } | undefined;
  isSaving: boolean;
  isAIChatOpen: boolean;
  setIsAIChatOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  isRefining: boolean;
  parsedPlan: EpicDocument | null;
  updateParsedPlan: (updater: (doc: EpicDocument) => void) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

export const PlanContext = createContext<PlanContextType | undefined>(undefined);

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

  const { plan, syncStatus, isLoading: planLoading, isError: planError, reloadFromDisk } = usePlan(planId);
  const { epics: apiEpics, isLoading: epicsLoading, isError: epicsError, updateEpicState } = useEpics(planId);
  const { dag } = useDAG(planId);
  const { progress, isLoading: isProgressLoading } = useWarRoomProgress(planId);
  
  const [selectedEpicRef, setSelectedEpicRef] = useState<string | null>(null);
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(true);
  const [isAIChatOpen, setIsAIChatOpen] = useState(false);
  // Initialize tab from URL ?tab= param, then manage via React state (SPA — no reloads)
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [planContent, setPlanContent] = useState('');
  const [parsedPlan, setParsedPlan] = useState<EpicDocument | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Undo/Redo Stack
  const [undoStack, setUndoStack] = useState<{ past: string[]; future: string[] }>({ past: [], future: [] });

  const pushToUndo = useCallback((content: string) => {
    setUndoStack(prev => ({
      past: [content, ...prev.past].slice(0, 50),
      future: []
    }));
  }, []);

  const undo = useCallback(() => {
    if (undoStack.past.length === 0) return;
    const nextContent = undoStack.past[0];
    const newPast = undoStack.past.slice(1);
    const newFuture = [planContent, ...undoStack.future].slice(0, 50);
    
    setUndoStack({ past: newPast, future: newFuture });
    setPlanContent(nextContent);
  }, [undoStack, planContent]);

  const redo = useCallback(() => {
    if (undoStack.future.length === 0) return;
    const nextContent = undoStack.future[0];
    const newFuture = undoStack.future.slice(1);
    const newPast = [planContent, ...undoStack.past].slice(0, 50);
    
    setUndoStack({ past: newPast, future: newFuture });
    setPlanContent(nextContent);
  }, [undoStack, planContent]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        redo();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, redo]);

  useEffect(() => {
    if (planContent) {
      try {
        const parsed = parseEpicMarkdown(planContent);
        setParsedPlan(parsed);
      } catch (err) {
        console.error('Failed to parse plan:', err);
        setParsedPlan(null);
      }
    }
  }, [planContent]);

  const updateParsedPlan = useCallback((updater: (doc: EpicDocument) => void) => {
    if (!parsedPlan) return;
    
    // Save current content to undo stack BEFORE updating
    pushToUndo(planContent);
    
    // We create a new doc object and shallow copy epics to allow the updater to replace them.
    const docCopy: EpicDocument = {
      ...parsedPlan,
      epics: parsedPlan.epics.map(e => ({
        ...e,
        frontmatter: new Map(e.frontmatter),
        sections: e.sections.map(s => ({
          ...s,
          items: s.items ? s.items.map(i => ({ ...i })) : undefined,
          tasks: s.tasks ? s.tasks.map(t => ({ ...t })) : undefined,
        }))
      }))
    };
    
    updater(docCopy);
    const newContent = serializeEpicMarkdown(docCopy);
    setPlanContent(newContent);
    setParsedPlan(docCopy);
  }, [parsedPlan, planContent, pushToUndo]);
  const addToast = useNotificationStore((state) => state.addToast);

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
      addToast({
        type: 'success',
        title: 'Plan Saved',
        message: 'Your plan changes have been successfully persisted.',
        autoDismiss: true,
      });
    } catch (err: unknown) {
      addToast({
        type: 'error',
        title: 'Save Failed',
        message: err instanceof Error ? err.message : 'There was an error saving your plan. Please try again.',
        autoDismiss: false,
      });
    } finally {
      setIsSaving(false);
    }
  }, [planId, planContent, addToast]);

  const launchPlan = useCallback(async () => {
    try {
      await savePlan();
      await apiPost('/run', { plan: planContent, plan_id: planId });
      addToast({
        type: 'success',
        title: 'Plan Launched',
        message: 'Your plan is now running.',
        autoDismiss: true,
      });
    } catch (err: unknown) {
      addToast({
        type: 'error',
        title: 'Launch Failed',
        message: err instanceof Error ? err.message : 'There was an error launching your plan. Please try again.',
        autoDismiss: false,
      });
    }
  }, [savePlan, planContent, planId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleApplyAI = useCallback((newContent: string) => {
    setPlanContent(newContent);
    setActiveTab('editor');
  }, []);

  // Synthesize epics from progress + DAG when the /epics API returns empty
  const epics = useMemo(() => {
    if (apiEpics && apiEpics.length > 0) {
      // Ensure role is populated from DAG if missing in the API response
      if (dag?.nodes) {
        return apiEpics.map(e => ({
          ...e,
          role: e.role || dag.nodes[e.epic_ref]?.role || 'unknown'
        }));
      }
      return apiEpics;
    }
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
    progress,
    isLoading: planLoading || epicsLoading,
    isProgressLoading,
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
    reloadFromDisk,
    syncStatus,
    isSaving,
    isAIChatOpen,
    setIsAIChatOpen,
    isRefining,
    parsedPlan,
    updateParsedPlan,
    undo,
    redo,
    canUndo: undoStack.past.length > 0,
    canRedo: undoStack.future.length > 0,
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
            {syncStatus && !syncStatus.in_sync && (
              <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between animate-in fade-in slide-in-from-top duration-300">
                <div className="flex items-center gap-2 text-amber-800 text-sm font-medium">
                  <span className="material-symbols-outlined text-amber-500" style={{ fontSize: '20px' }}>warning</span>
                  Plan changed on disk externally.
                </div>
                <button 
                  onClick={() => reloadFromDisk()}
                  className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded shadow-sm transition-colors flex items-center gap-1"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>sync</span>
                  Reload from Disk
                </button>
              </div>
            )}
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

          {/* Right Panel: AI Chat (moved to AI Plan tab) */}
        </div>

        {/* Progress Footer */}
        <ProgressFooter />
      </div>
    </PlanContext.Provider>
  );
}
