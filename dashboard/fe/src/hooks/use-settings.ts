'use client';

import useSWR, { mutate } from 'swr';
import { useEffect } from 'react';
import { apiPut, apiPost, fetcher } from '@/lib/api-client';
import { useSharedWebSocket } from '@/components/providers/WebSocketProvider';
import { useNotificationStore } from '@/lib/stores/notificationStore';

import type { MasterSettings, EffectiveResolution, ProviderTestResult, VaultInfo, OpenCodeSyncResult } from '@/types/settings';

export function useSettings() {
  const { addToast } = useNotificationStore();
  const { data: settings, error: settingsError, mutate: mutateSettings } = useSWR<MasterSettings>(
    '/settings',
    fetcher,
    { revalidateOnFocus: false }
  );

  const updateNamespace = async (namespace: string, value: unknown) => {
    await apiPut(`/settings/${namespace}`, value);
    await mutateSettings();
  };

  const resetNamespace = async (namespace: string) => {
    await apiPost(`/settings/reset/${namespace}`);
    await mutateSettings();
  };

  const testProvider = async (provider: string): Promise<ProviderTestResult> => {
    const result = await apiPost<ProviderTestResult>(`/settings/test/${provider}`);
    await mutateSettings();
    return result;
  };

  const updateVault = async (scope: string, key: string, secret: string) => {
    await apiPost(`/settings/vault/${scope}/${key}`, { value: secret });
    await mutateSettings();
  };

  const { lastMessage } = useSharedWebSocket();


  useEffect(() => {
    if (lastMessage && (lastMessage.type === 'settings_updated' || lastMessage.event === 'settings_updated')) {
      const namespace = lastMessage.namespace || lastMessage.data?.namespace || 'settings';
      addToast({
        type: 'success',
        title: 'Settings Updated',
        message: `Changes saved to ${namespace}`,
        autoDismiss: true,
      });
      mutateSettings();
      mutate((key) => typeof key === 'string' && key.includes('/settings/effective'));
    }
  }, [lastMessage, mutateSettings, addToast]);

  const { data: vaultInfo, mutate: mutateVaultInfo } = useSWR<VaultInfo>(
    '/settings/vault/status',
    fetcher,
    { revalidateOnFocus: false }
  );

  const syncOpenCode = async (): Promise<OpenCodeSyncResult> => {
    return apiPost<OpenCodeSyncResult>('/settings/opencode/sync');
  };

  return {
    settings,
    isLoading: !settings && !settingsError,
    isError: !!settingsError,
    updateNamespace,
    resetNamespace,
    testProvider,
    updateVault,
    vaultInfo,
    refreshVaultInfo: mutateVaultInfo,
    syncOpenCode,
  };
}

export function useEffectiveSettings(role: string, planId?: string, taskRef?: string) {
  const params = new URLSearchParams({ role });
  if (planId) params.append('plan_id', planId);
  if (taskRef) params.append('task_ref', taskRef);

  const { data, error, mutate: mutateEffective } = useSWR<EffectiveResolution>(
    `/settings/effective?${params.toString()}`,
    fetcher,
    { revalidateOnFocus: false }
  );

  return {
    data,
    isLoading: !data && !error,
    isError: !!error,
    mutate: mutateEffective,
  };
}
