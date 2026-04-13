import useSWR from 'swr';
import { Plan } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

export function usePlans(search?: string) {
  const isMockRealtime = process.env.NEXT_PUBLIC_ENABLE_MOCK_REALTIME === 'true';
  const q = search?.trim() || '';
  const swrKey = q ? `/plans?q=${encodeURIComponent(q)}` : '/plans';
  const { data, error, mutate, isLoading } = useSWR<Plan[]>(swrKey, {
    refreshInterval: isMockRealtime ? 10000 : 0,
  });

  const createPlan = async (plan: Partial<Plan>) => {
    const newPlan = await apiPost<Plan>('/plans/create', plan);
    mutate((plans) => (plans ? [...plans, newPlan] : [newPlan]), false);
    return newPlan;
  };

  return {
    plans: data,
    isLoading,
    isError: error,
    createPlan,
    refresh: mutate,
  };
}

interface PlanDetailResponse {
  plan: Plan;
  epics: unknown[];
}

export function usePlan(id: string) {
  const isMockRealtime = process.env.NEXT_PUBLIC_ENABLE_MOCK_REALTIME === 'true';
  const { data, error, mutate, isLoading } = useSWR<PlanDetailResponse>(id ? `/plans/${id}` : null, {
    refreshInterval: isMockRealtime ? 10000 : 0,
  });

  const { data: syncData, mutate: refreshSyncStatus } = useSWR<{ in_sync: boolean; disk_mtime: number; zvec_mtime: number }>(id ? `/plans/${id}/sync-status` : null, {
    refreshInterval: 15000, // Check every 15 seconds
  });

  const plan = data?.plan ?? (data as unknown as Plan | undefined);

  const updatePlan = async (updates: Partial<Plan>) => {
    const updatedPlan = await apiPut<Plan>(`/plans/${id}`, updates);
    mutate(undefined, { revalidate: true });
    return updatedPlan;
  };

  const deletePlan = async () => {
    await apiDelete(`/plans/${id}`);
    mutate(undefined, false);
  };

  const reloadFromDisk = async () => {
    await apiPost(`/plans/${id}/reload`, {});
    mutate(undefined, { revalidate: true });
    refreshSyncStatus();
  };

  return {
    plan,
    syncStatus: syncData,
    isLoading,
    isError: error,
    updatePlan,
    deletePlan,
    reloadFromDisk,
    refresh: mutate,
    refreshSyncStatus,
  };
}
