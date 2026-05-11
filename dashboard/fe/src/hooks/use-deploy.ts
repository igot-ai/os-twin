import useSWR from 'swr';
import { DeployStatus } from '@/types';
import { apiPost, ApiError } from '@/lib/api-client';
import { useNotificationStore } from '@/lib/stores/notificationStore';

export function useDeployStatus(planId: string | null) {
  const { data, error, mutate, isLoading } = useSWR<DeployStatus>(
    planId ? `/plans/${planId}/deploy/status` : null,
    {
      refreshInterval: 5000,
      revalidateOnFocus: true,
    }
  );

  const addToast = useNotificationStore((s) => s.addToast);

  const startPreview = async () => {
    if (!planId) return null;
    try {
      const result = await apiPost<DeployStatus>(`/plans/${planId}/deploy/start`);
      mutate(result, false);
      return result;
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Failed to start preview';
      addToast({ type: 'error', title: 'Preview Error', message: msg });
      return null;
    }
  };

  const stopPreview = async () => {
    if (!planId) return null;
    try {
      const result = await apiPost<DeployStatus>(`/plans/${planId}/deploy/stop`);
      mutate(result, false);
      return result;
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Failed to stop preview';
      addToast({ type: 'error', title: 'Preview Error', message: msg });
      return null;
    }
  };

  const restartPreview = async () => {
    if (!planId) return null;
    try {
      const result = await apiPost<DeployStatus>(`/plans/${planId}/deploy/restart`);
      mutate(result, false);
      return result;
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Failed to restart preview';
      addToast({ type: 'error', title: 'Preview Error', message: msg });
      return null;
    }
  };

  return {
    deployStatus: data,
    isLoading,
    isError: error,
    startPreview,
    stopPreview,
    restartPreview,
    refresh: mutate,
  };
}
