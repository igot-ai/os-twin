'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { usePlanContext } from './PlanWorkspace';
import KnowledgeTabCore, { KnowledgeTabCoreProps } from '@/components/knowledge/KnowledgeTabCore';
import { useKnowledgeNamespaces } from '@/hooks/use-knowledge-namespaces';
import { useNotificationStore } from '@/lib/stores/notificationStore';

/**
 * Sanitizes a plan ID to be a valid namespace name.
 * Namespace names should be alphanumeric with hyphens and underscores.
 * 
 * @param planId - The raw plan ID
 * @returns A sanitized namespace name
 */
function sanitizeNamespaceName(planId: string): string {
  // Replace invalid characters with hyphens
  // Keep alphanumeric, hyphens, and underscores
  let sanitized = planId.replace(/[^a-zA-Z0-9_-]/g, '-');
  
  // Ensure it doesn't start with a number (some systems don't like this)
  if (/^\d/.test(sanitized)) {
    sanitized = 'plan-' + sanitized;
  }
  
  // Limit length to 63 characters (Kubernetes/DNS label limit)
  if (sanitized.length > 63) {
    sanitized = sanitized.substring(0, 63);
  }
  
  return sanitized || 'default-plan-namespace';
}

/**
 * PlanKnowledgeTab is a wrapper component that bridges PlanContext
 * to the decoupled KnowledgeTabCore component.
 * 
 * This component:
 * 1. Reads plan-specific state from PlanContext
 * 2. Passes it as props to KnowledgeTabCore
 * 3. Handles the Memory↔Knowledge bridge (highlight note, tab switching)
 * 4. Auto-creates a namespace matching the plan_id (lazy creation on first open)
 */
export default function PlanKnowledgeTab() {
  const { planId, setActiveTab, setHighlightNoteId } = usePlanContext();
  const router = useRouter();
  const addToast = useNotificationStore((state) => state.addToast);
  
  // Sanitize plan ID for use as namespace name
  const namespaceName = sanitizeNamespaceName(planId);
  
  // Track whether we've attempted auto-create (prevents infinite loops)
  const hasAttemptedCreate = useRef(false);
  
  // Track if namespace is ready (exists or was created)
  const [isNamespaceReady, setIsNamespaceReady] = useState(false);
  
  // Fetch namespaces to check if plan namespace exists
  const { namespaces, isLoading, createNamespace, refresh } = useKnowledgeNamespaces();
  
  // Auto-create namespace if it doesn't exist (lazy creation)
  useEffect(() => {
    // Skip if still loading or already attempted
    if (isLoading || hasAttemptedCreate.current) return;
    
    // Check if namespace already exists
    const namespaceExists = namespaces?.some(ns => ns.name === namespaceName);
    
    if (namespaceExists) {
      setIsNamespaceReady(true);
      return;
    }
    
    // Mark as attempted to prevent race conditions
    hasAttemptedCreate.current = true;
    
    // Create the namespace
    const createPlanNamespace = async () => {
      try {
        await createNamespace({
          name: namespaceName,
          description: `Knowledge for plan ${planId}`,
        });
        setIsNamespaceReady(true);
        addToast({
          type: 'success',
          title: 'Namespace Created',
          message: `Created knowledge namespace "${namespaceName}" for this plan.`,
          autoDismiss: true,
        });
      } catch (err) {
        // Log error but don't block the UI - user can still use other namespaces
        console.error('Failed to create plan namespace:', err);
        // Still mark as ready so the UI doesn't hang
        setIsNamespaceReady(true);
        addToast({
          type: 'warning',
          title: 'Namespace Creation Failed',
          message: `Could not create namespace "${namespaceName}". You can select an existing namespace or create one manually.`,
          autoDismiss: false,
        });
      }
    };
    
    createPlanNamespace();
  }, [namespaces, isLoading, namespaceName, planId, createNamespace, addToast]);
  
  // Handle clicking a memory note from the BacklinkBadge - switch to Memory tab
  const handleNoteClick = useCallback((noteId: string) => {
    // Set the note to highlight in MemoryTab
    setHighlightNoteId(noteId);
    // Switch to the Memory tab
    setActiveTab('memory');
  }, [setActiveTab, setHighlightNoteId]);
  
  // Handle "View All Knowledge" navigation
  const handleViewAllKnowledge = useCallback(() => {
    router.push(`/knowledge?ns=${encodeURIComponent(namespaceName)}`);
  }, [router, namespaceName]);
  
  // Props for KnowledgeTabCore — plan context scopes to the plan namespace only
  const coreProps: KnowledgeTabCoreProps = {
    onNoteClick: handleNoteClick,
    defaultNamespace: namespaceName,
    headerVariant: 'full',
    isPlanContext: true,
    planNamespaceName: namespaceName,
    onViewAllKnowledge: handleViewAllKnowledge,
    showMetrics: false,
    filterNamespace: namespaceName,
  };
  
  // Show loading state while checking/creating namespace
  if (isLoading || !isNamespaceReady) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <div 
            className="w-10 h-10 border-2 border-t-transparent rounded-full animate-spin mx-auto"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} 
          />
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Initializing plan knowledge...
          </p>
        </div>
      </div>
    );
  }
  
  return <KnowledgeTabCore {...coreProps} />;
}
