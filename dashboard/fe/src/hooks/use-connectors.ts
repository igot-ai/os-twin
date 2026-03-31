import useSWR from 'swr';
import { apiPost } from '@/lib/api-client';

export interface ConnectorsConfig {
  adapters: Record<string, Record<string, string>>;
  registered_platforms: string[];
  settings: {
    important_events: string[];
    enabled_platforms: string[];
  };
}

export function useConnectors() {
  const { data, error, mutate, isLoading } = useSWR<ConnectorsConfig>('/chat-adapters/config');

  const updateConfig = async (platform: string, config: Record<string, string>) => {
    await apiPost('/chat-adapters/config', { platform, config });
    mutate();
  };

  const updateSettings = async (settings: { important_events: string[]; enabled_platforms: string[] }) => {
    await apiPost('/chat-adapters/settings', settings);
    mutate();
  };

  const testConnector = async (platform: string) => {
    return apiPost<{ status: string }>(`/chat-adapters/${platform}/test`);
  };

  return {
    config: data,
    isLoading,
    isError: error,
    updateConfig,
    updateSettings,
    testConnector,
    refresh: mutate,
  };
}
