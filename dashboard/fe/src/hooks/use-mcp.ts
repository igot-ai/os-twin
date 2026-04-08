import useSWR from 'swr';
import { apiPost, apiDelete, apiPut } from '@/lib/api-client';

export interface McpServer {
  name: string;
  type: 'local' | 'remote' | 'stdio' | 'http';
  status: string;
  credential_status: 'ok' | 'missing';
  missing_keys: string[];
  builtin: boolean;
  config: any;
}

export interface TestAllServer {
  name: string;
  status: 'connected' | 'failed';
  message: string;
  details: string[];
  command?: string;
}

export interface TestAllResult {
  servers: TestAllServer[];
  total: number;
  connected: number;
  failed: number;
  error?: string;
  raw_output?: string;
}

export function useMcpServers() {
  const { data, error, mutate, isLoading } = useSWR<{ servers: McpServer[] }>('/mcp/servers');

  const addServer = async (server: any) => {
    const res = await apiPost('/mcp/servers', server);
    mutate();
    return res;
  };

  const removeServer = async (name: string) => {
    const res = await apiDelete(`/mcp/servers/${name}`);
    mutate();
    return res;
  };

  const testServer = async (name: string) => {
    const res = await apiPost<{ status: string; message: string }>(`/mcp/servers/${name}/test`, {});
    return res;
  };

  const testAllServers = async () => {
    const res = await apiPost<TestAllResult>('/mcp/servers/test-all', {});
    return res;
  };

  return {
    servers: data?.servers,
    isLoading,
    isError: error,
    addServer,
    removeServer,
    testServer,
    testAllServers,
    refresh: mutate,
  };
}

export function useMcpCredentials(serverName: string) {
  const { data, error, mutate, isLoading } = useSWR<{ credentials: any[] }>(
    serverName ? `/mcp/servers/${serverName}/credentials` : null
  );

  const setCredential = async (vaultServer: string, key: string, value: string) => {
    const fullKey = vaultServer === serverName ? key : `${vaultServer}/${key}`;
    const res = await apiPut(`/mcp/servers/${serverName}/credentials/${fullKey}`, { value });
    mutate();
    return res;
  };

  const deleteCredential = async (vaultServer: string, key: string) => {
    const fullKey = vaultServer === serverName ? key : `${vaultServer}/${key}`;
    const res = await apiDelete(`/mcp/servers/${serverName}/credentials/${fullKey}`);
    mutate();
    return res;
  };

  return {
    credentials: data?.credentials,
    isLoading,
    isError: error,
    setCredential,
    deleteCredential,
    refresh: mutate,
  };
}
