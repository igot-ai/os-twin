'use client';

import { useState, useEffect, useCallback } from 'react';
import { Plan, Project } from '@/types';
import { apiGet } from '@/lib/api';

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  const loadProjects = useCallback(async () => {
    try {
      const data = await apiGet<{ plans: Plan[] }>('/api/plans');
      const allPlans = data.plans || [];
      setPlans(allPlans);

      const grouped = new Map<string, Plan[]>();
      for (const plan of allPlans) {
        const dir = plan.working_dir || '.';
        if (!grouped.has(dir)) grouped.set(dir, []);
        grouped.get(dir)!.push(plan);
      }

      const derived: Project[] = Array.from(grouped.entries())
        .map(([path, dirPlans]) => ({
          name: path.split('/').filter(Boolean).pop() || path,
          path,
          plans: dirPlans.sort((a, b) => b.created_at.localeCompare(a.created_at)),
          planCount: dirPlans.length,
          epicCount: dirPlans.reduce((sum, p) => sum + (p.epic_count || 0), 0),
        }))
        .sort((a, b) => b.planCount - a.planCount);

      setProjects(derived);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  return { projects, plans, loading, reload: loadProjects };
}
