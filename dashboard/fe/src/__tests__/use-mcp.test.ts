import { describe, it, expect, vi } from 'vitest';
import { useMcpServers, useMcpCredentials } from '../hooks/use-mcp';
import useSWR from 'swr';
import { apiPost, apiDelete, apiPut } from '@/lib/api-client';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
  apiPut: vi.fn(),
}));

describe('useMcpServers', () => {
  it('should return servers data', () => {
    const mockData = {
      servers: [
        { name: 'test-server', type: 'stdio', status: 'active' }
      ]
    };
    (useSWR as any).mockReturnValue({
      data: mockData,
      error: undefined,
      mutate: vi.fn(),
      isLoading: false
    });

    const { servers } = useMcpServers();
    expect(servers).toEqual(mockData.servers);
  });

  it('should add server with store_in_vault', async () => {
    (useSWR as any).mockReturnValue({ mutate: vi.fn() });
    const { addServer } = useMcpServers();
    await addServer({ name: 'new', type: 'stdio', store_in_vault: true });
    expect(apiPost).toHaveBeenCalledWith('/mcp/servers', { name: 'new', type: 'stdio', store_in_vault: true });
  });
});

describe('useMcpCredentials', () => {
  it('should call apiPut with simplified path when vaultServer matches serverName', async () => {
    (useSWR as any).mockReturnValue({
      data: { credentials: [] },
      mutate: vi.fn(),
    });

    const { setCredential } = useMcpCredentials('test-server');
    await setCredential('test-server', 'key1', 'val1');
    
    expect(apiPut).toHaveBeenCalledWith('/mcp/servers/test-server/credentials/key1', { value: 'val1' });
  });

  it('should call apiPut with combined path when vaultServer differs from serverName', async () => {
    (useSWR as any).mockReturnValue({
      data: { credentials: [] },
      mutate: vi.fn(),
    });

    const { setCredential } = useMcpCredentials('test-server');
    await setCredential('other-server', 'key1', 'val1');
    
    expect(apiPut).toHaveBeenCalledWith('/mcp/servers/test-server/credentials/other-server/key1', { value: 'val1' });
  });

  it('should delete credential with simplified path', async () => {
    (useSWR as any).mockReturnValue({
      data: { credentials: [] },
      mutate: vi.fn(),
    });

    const { deleteCredential } = useMcpCredentials('test-server');
    await deleteCredential('test-server', 'key1');
    
    expect(apiDelete).toHaveBeenCalledWith('/mcp/servers/test-server/credentials/key1');
  });
});
