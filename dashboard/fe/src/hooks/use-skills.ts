import useSWR from 'swr';
import { Skill } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

export function useSkills(category?: string, role?: string, query?: string) {
  let url = '/skills';
  if (query) {
    url = '/skills/search';
  }
  const params = new URLSearchParams();
  if (query) params.append('q', query);
  if (category) params.append('category', category);
  if (role) params.append('role', role);
  if (params.toString()) url += `?${params.toString()}`;

  const { data, error, mutate, isLoading } = useSWR<Skill[]>(url);

  const createSkill = async (skill: Partial<Skill>) => {
    const newSkill = await apiPost<Skill>('/skills', skill);
    mutate();
    return newSkill;
  };

  const syncWithDisk = async () => {
    const result = await apiPost<{synced_count: number}>('/skills/sync', {});
    mutate();
    return result;
  };

  return {
    skills: data,
    isLoading,
    isError: error,
    createSkill,
    syncWithDisk,
    refresh: mutate,
  };
}

export function useSkillValidation() {
  const validateSkill = async (content: string) => {
    return await apiPost<{valid: boolean, errors: string[], warnings: string[], markers: any[]}>('/skills/validate', { content });
  };

  return { validateSkill };
}

export function useSkill(id: string) {
  const { data, error, mutate, isLoading } = useSWR<Skill>(id ? `/skills/${id}` : null);

  const updateSkill = async (updates: Partial<Skill>) => {
    const updatedSkill = await apiPut<Skill>(`/skills/${id}`, updates);
    mutate(updatedSkill, false);
    return updatedSkill;
  };

  const deleteSkill = async () => {
    await apiDelete(`/skills/${id}`);
    mutate(undefined, false);
  };

  return {
    skill: data,
    isLoading,
    isError: error,
    updateSkill,
    deleteSkill,
    refresh: mutate,
  };
}
