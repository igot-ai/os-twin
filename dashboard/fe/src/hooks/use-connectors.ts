import useSWR from 'swr';
import { Connector, ConnectorInstance, ExternalDocumentList } from '@/types';
import { apiPost, apiPut, apiDelete } from '@/lib/api-client';

/**
 * Hook for fetching the available connector types from the registry.
 */
export function useConnectorRegistry() {
  const { data, error, isLoading } = useSWR<Connector[]>('/connectors/registry');

  return {
    registry: data,
    isLoading,
    isError: error,
  };
}

/**
 * Hook for managing connector instances.
 */
export function useConnectorInstances() {
  const { data, error, mutate, isLoading } = useSWR<ConnectorInstance[]>('/connectors/instances');

  const createInstance = async (req: { 
    connector_id: string; 
    name: string; 
    config: Record<string, unknown>; 
    store_in_vault?: boolean 
  }) => {
    const newInstance = await apiPost<ConnectorInstance>('/connectors/instances', req);
    mutate((instances) => (instances ? [...instances, newInstance] : [newInstance]), false);
    return newInstance;
  };

  return {
    instances: data,
    isLoading,
    isError: error,
    createInstance,
    refresh: mutate,
  };
}

/**
 * Hook for a single connector instance operations.
 */
export function useConnectorInstance(id: string | null) {
  const { data, error, mutate, isLoading } = useSWR<ConnectorInstance>(
    id ? `/connectors/instances/${id}` : null
  );

  const updateInstance = async (updates: { 
    name?: string; 
    enabled?: boolean; 
    config?: Record<string, unknown>; 
    store_in_vault?: boolean 
  }) => {
    if (!id) return;
    const updated = await apiPut<ConnectorInstance>(`/connectors/instances/${id}`, updates);
    mutate(updated, false);
    return updated;
  };

  const deleteInstance = async () => {
    if (!id) return;
    await apiDelete(`/connectors/instances/${id}`);
    mutate(undefined, false);
  };

  const validateInstance = async () => {
    if (!id) return;
    return apiPost<{ status: string; message?: string }>(`/connectors/instances/${id}/validate`);
  };

  return {
    instance: data,
    isLoading,
    isError: error,
    updateInstance,
    deleteInstance,
    validateInstance,
    refresh: mutate,
  };
}

/**
 * Hook for browsing documents from a connector instance.
 */
export function useConnectorDocuments(id: string | null, cursor?: string) {
  const query = cursor ? `?cursor=${cursor}` : '';
  const { data, error, isLoading, mutate } = useSWR<ExternalDocumentList>(
    id ? `/connectors/instances/${id}/documents${query}` : null
  );

  return {
    documents: data?.documents,
    nextCursor: data?.nextCursor,
    hasMore: data?.hasMore,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
