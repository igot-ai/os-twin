import useSWR from 'swr';
import { Role } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

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
    return apiPost(`/roles/${id}/test`);
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
