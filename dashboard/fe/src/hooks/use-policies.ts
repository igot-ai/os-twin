import useSWR from 'swr';
import { Policy, PolicyExecutionResult } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

/**
 * Hook for managing policies.
 */
export function usePolicies(roleId?: string) {
  let url = '/policies';
  const { data, error, mutate, isLoading } = useSWR<Policy[]>(url);

  const rolePolicies = roleId && data ? data.filter(p => p.trigger.role_id === roleId) : data;

  const createPolicy = async (policy: Partial<Policy>) => {
    const newPolicy = await apiPost<Policy>('/policies', policy);
    mutate((policies) => (policies ? [...policies, newPolicy] : [newPolicy]), false);
    return newPolicy;
  };

  const updatePolicy = async (id: string, updates: Partial<Policy>) => {
    const updated = await apiPut<Policy>(`/policies/${id}`, updates);
    mutate((policies) => policies?.map(p => p.policy_id === id ? updated : p), false);
    return updated;
  };

  const deletePolicy = async (id: string) => {
    await apiDelete(`/policies/${id}`);
    mutate((policies) => policies?.filter(p => p.policy_id !== id), false);
  };

  const executePolicy = async (id: string) => {
    return await apiPost<PolicyExecutionResult>(`/policies/${id}/execute`);
  };

  return {
    policies: rolePolicies,
    allPolicies: data,
    isLoading,
    isError: error,
    createPolicy,
    updatePolicy,
    deletePolicy,
    executePolicy,
    refresh: mutate,
  };
}

/**
 * Hook for a single policy.
 */
export function usePolicy(id: string | null) {
  const { data, error, mutate, isLoading } = useSWR<Policy>(
    id ? `/policies/${id}` : null
  );

  return {
    policy: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook for policy execution history.
 */
export function usePolicyHistory(policyId: string | null) {
  const { data, error, isLoading } = useSWR<PolicyExecutionResult[]>(
    policyId ? `/policies/${policyId}/history` : null
  );

  return {
    history: data,
    isLoading,
    isError: error,
  };
}
