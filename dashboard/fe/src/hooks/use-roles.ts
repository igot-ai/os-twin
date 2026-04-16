import useSWR from 'swr';
import { Role } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';
import type { ModelInfo } from '@/types/settings';

export function useRoles() {
  const { data, error, mutate, isLoading } = useSWR<Role[]>('/roles');

  const createRole = async (role: Partial<Role>) => {
    const newRole = await apiPost<Role>('/roles', role);
    mutate((roles) => (roles ? [...roles, newRole] : [newRole]), false);
    return newRole;
  };

  return {
    roles: data,
    isLoading,
    isError: error,
    createRole,
    refresh: mutate,
  };
}

export function useModelRegistry() {
  const { data, error, isLoading } = useSWR<Record<string, ModelInfo[]>>(
    '/models/registry',
  );

  // Flat list of all models for populating ModelSelect
  const allModels: ModelInfo[] = data
    ? Object.values(data).flat()
    : [];

  // Provider-keyed map: provider_id → first logo/name found
  const providers: Record<string, { name: string; logo_url: string }> = {};
  if (data) {
    for (const models of Object.values(data)) {
      for (const m of models) {
        const pid = m.provider_id || '_other';
        if (!providers[pid]) {
          providers[pid] = {
            name: pid,
            logo_url: m.logo_url || `https://models.dev/logos/${pid}.svg`,
          };
        }
      }
    }
  }

  return {
    registry: data,
    allModels,
    providers,
    isLoading,
    isError: error,
  };
}

export function useRoleDependencies(id: string) {
  const { data, error, isLoading } = useSWR<{ active_warrooms: any[]; inactive_warrooms: any[]; plans: string[] }>(id ? `/roles/${id}/dependencies` : null);

  return {
    dependencies: data,
    isLoading,
    isError: error,
  };
}

export function useRole(id: string) {
  const { data, error, mutate, isLoading } = useSWR<Role>(id ? `/roles/${id}` : null);

  const updateRole = async (updates: Partial<Role>) => {
    const updatedRole = await apiPut<Role>(`/roles/${id}`, updates);
    mutate(updatedRole, false);
    return updatedRole;
  };

  const deleteRole = async () => {
    await apiDelete(`/roles/${id}`);
    mutate(undefined, false);
  };

  const testRole = async () => {
    if (!data?.version) throw new Error('Role version not available');
    return apiPost(`/models/${data.version}/test`);
  };

  return {
    role: data,
    isLoading,
    isError: error,
    updateRole,
    deleteRole,
    testRole,
    refresh: mutate,
  };
}
