'use client';

import { useState, useEffect, useCallback } from 'react';
import { Plan, Epic } from '@/types';
import { apiGet } from '@/lib/api';

export interface IssueEpic extends Epic {
  plan_title: string;
}

export function useIssues() {
  const [issues, setIssues] = useState<IssueEpic[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  const loadIssues = useCallback(async () => {
    try {
      const planData = await apiGet<{ plans: Plan[] }>('/api/plans');
      const allPlans = planData.plans || [];
      setPlans(allPlans);

      const results = await Promise.allSettled(
        allPlans.map(async (plan) => {
          const data = await apiGet<{ epics?: Epic[] }>(`/api/plans/${plan.plan_id}`);
          return (data.epics || []).map((epic) => ({ ...epic, plan_title: plan.title }));
        }),
      );

      const allIssues: IssueEpic[] = [];
      for (const result of results) {
        if (result.status === 'fulfilled') allIssues.push(...result.value);
      }
      setIssues(allIssues);
    } catch (err) {
      console.error('Failed to load issues:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  return { issues, plans, loading, reload: loadIssues };
}
