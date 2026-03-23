'use client';

import { useState, useMemo, useEffect } from 'react';
import { Room, Plan } from '@/types';
import { apiGet } from '@/lib/api';

export interface ResolvedSkill {
  name: string;
  trust_level: string;
}

export interface RoleConfig {
  name: string;
  description: string;
  default_model: string;
  timeout_seconds: number;
  capabilities?: string[];
  supported_task_types?: string[];
  resolved_skills?: ResolvedSkill[];
}

export interface AgentSummary {
  name: string;
  icon: string;
  config: RoleConfig | null;
  status: 'running' | 'idle';
  activeRooms: number;
  completedRooms: number;
  failedRooms: number;
  lastActivity: string | null;
}

const ROLE_ICONS: Record<string, string> = {
  manager: '⬡',
  engineer: '⚙',
  qa: '✦',
  architect: '◆',
  reporter: '📊',
  audit: '🔍',
};

const ROLE_STATUS_MAP: Record<string, string> = {
  engineering: 'engineer',
  fixing: 'engineer',
  'qa-review': 'qa',
  'architect-review': 'architect',
  'manager-triage': 'manager',
  pending: 'manager',
};

const DEFAULT_ROLES: RoleConfig[] = [
  {
    name: 'manager',
    description: 'Orchestration loop',
    default_model: 'gemini-3.1-pro-preview',
    timeout_seconds: 900,
  },
  {
    name: 'engineer',
    description: 'Software engineer',
    default_model: 'gemini-3-flash-preview',
    timeout_seconds: 600,
  },
  {
    name: 'qa',
    description: 'QA engineer',
    default_model: 'gemini-3-flash-preview',
    timeout_seconds: 600,
  },
  {
    name: 'architect',
    description: 'Software architect',
    default_model: 'gemini-3-flash-preview',
    timeout_seconds: 900,
  },
  {
    name: 'reporter',
    description: 'Report generator — creates structured PDF reports from data specs',
    default_model: 'gemini-3-flash-preview',
    timeout_seconds: 600,
  },
  {
    name: 'audit',
    description: 'Auditor — scopes risk investigations, validates findings, makes risk decisions',
    default_model: 'gemini-3.1-pro-preview',
    timeout_seconds: 900,
  },
];

export function useAgents(rooms: Room[]) {
  const [roleConfigs, setRoleConfigs] = useState<RoleConfig[]>(DEFAULT_ROLES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ plans: Plan[] }>('/api/plans')
      .then(async (planData) => {
        if (cancelled) return;
        const plans = planData.plans || [];
        const activePlan = plans.find((p) => p.status === 'launched') || plans[0];
        if (activePlan) {
          const data = await apiGet<{ roles: RoleConfig[] }>(
            `/api/plans/${activePlan.plan_id}/roles`,
          );
          if (!cancelled && data.roles?.length) setRoleConfigs(data.roles);
        }
      })
      .catch(() => {
        /* use defaults */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const agents: AgentSummary[] = useMemo(() => {
    return roleConfigs.map((cfg) => {
      const activeRooms = rooms.filter((r) => {
        const activeRole = ROLE_STATUS_MAP[r.status];
        return activeRole === cfg.name;
      });
      const passed = rooms.filter((r) => r.status === 'passed').length;
      const failed = rooms.filter((r) => r.status === 'failed-final').length;

      const lastActivity = activeRooms
        .map((r) => r.last_activity)
        .filter(Boolean)
        .sort()
        .pop();

      return {
        name: cfg.name,
        icon: ROLE_ICONS[cfg.name] || '●',
        config: cfg,
        status: activeRooms.length > 0 ? ('running' as const) : ('idle' as const),
        activeRooms: activeRooms.length,
        completedRooms: passed,
        failedRooms: failed,
        lastActivity: lastActivity || null,
      };
    });
  }, [roleConfigs, rooms]);

  return { agents, roleConfigs, loading };
}
