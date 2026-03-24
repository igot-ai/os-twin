import useSWR from 'swr';
import { Skill } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

export function useSkills(category?: string, role?: string) {
  let url = '/skills';
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  if (role) params.append('role', role);
  if (params.toString()) url += `?${params.toString()}`;

  const { data, error, mutate, isLoading } = useSWR<Skill[]>(url);

  const createSkill = async (skill: Partial<Skill>) => {
    const newSkill = await apiPost<Skill>('/skills', skill);
    mutate((skills) => (skills ? [...skills, newSkill] : [newSkill]), false);
    return newSkill;
  };

  return {
    skills: data,
    isLoading,
    isError: error,
    createSkill,
    refresh: mutate,
  };
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
