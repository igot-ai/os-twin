'use client';

import useSWR from 'swr';
import {
  WarRoomProgress,
  Lifecycle,
  AuditLogEntry,
  AgentInstance,
  WarRoomConfig,
  ChannelMessage,
} from '@/types';

/**
 * Fetch plan-level progress (progress.json).
 */
export function useWarRoomProgress(planId: string) {
  const { data, error, mutate, isLoading } = useSWR<WarRoomProgress>(
    planId ? `/plans/${planId}/progress` : null
  );

  return {
    progress: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch lifecycle state machine for a specific epic's war room.
 */
export function useLifecycle(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<Lifecycle>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/lifecycle` : null
  );

  return {
    lifecycle: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch audit log entries for a specific epic's war room.
 */
export function useAuditLog(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<AuditLogEntry[]>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/audit` : null
  );

  return {
    auditLog: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch brief.md content for a specific epic's war room.
 */
export function useBrief(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<{ content: string; working_dir: string; created_at: string }>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/brief` : null
  );

  return {
    brief: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch artifacts listing for a specific epic's war room.
 */
export function useArtifacts(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<{ name: string; size: number; type: string }[]>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/artifacts` : null
  );

  return {
    artifacts: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch agent instances for a specific epic's war room.
 */
export function useAgentInstances(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<AgentInstance[]>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/agents` : null
  );

  return {
    agents: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Fetch war room config for a specific epic.
 */
export function useWarRoomConfig(planId: string, epicRef: string) {
  const { data, error, mutate, isLoading } = useSWR<WarRoomConfig>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/config` : null
  );

  return {
    config: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
