import useSWR from 'swr';
import { Skill } from '@/types';
import { apiPost, apiPut, apiDelete, apiPatch } from '@/lib/api-client';

export function useSkills(category?: string, role?: string, query?: string, includeDisabled: boolean = false) {
  let url = '/skills';
  if (query) {
    url = '/skills/search';
  }
  const params = new URLSearchParams();
  if (query) params.append('q', query);
  if (category) params.append('category', category);
  if (role) params.append('role', role);
  if (includeDisabled) params.append('include_disabled', 'true');
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

export interface ClawhubSkill {
  name: string;
  slug: string;
  description: string;
  author?: string;
  tags?: string[];
  category?: string;
  downloads?: number;
  installs?: number;
  version?: string;
  score?: number;
}

export interface ClawhubInstalledSkill {
  slug: string;
  version?: string;
  installedAt?: number;
}

export function useClawhubInstalled() {
  const { data, mutate } = useSWR<ClawhubInstalledSkill[]>('/skills/clawhub-installed');
  const installedSlugs = new Set((data || []).map((s) => s.slug));
  return { installed: data || [], installedSlugs, refresh: mutate };
}

export function useClawhubSearch(query: string) {
  const url = query ? `/skills/clawhub-search?q=${encodeURIComponent(query)}` : null;
  const { data, error, isLoading } = useSWR<ClawhubSkill[]>(url);

  const installSkill = async (skillName: string) => {
    return await apiPost<{ status: string; skill: string; output: string }>(
      '/skills/clawhub-install',
      { skill_name: skillName },
      { headers: { 'X-Confirm-Install': 'true' } },
    );
  };

  return {
    results: data,
    isLoading,
    isError: error,
    installSkill,
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

  const toggleSkill = async () => {
    const updatedSkill = await apiPatch<Skill>(`/skills/${id}/toggle`, {});
    mutate(updatedSkill, false);
    return updatedSkill;
  };

  return {
    skill: data,
    isLoading,
    isError: error,
    updateSkill,
    deleteSkill,
    toggleSkill,
    refresh: mutate,
  };
}
