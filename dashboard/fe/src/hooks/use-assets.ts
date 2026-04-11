import useSWR from 'swr';
import { PlanAsset } from '@/types';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';
import { useCallback, useState } from 'react';

const assetFetcher = (url: string) => apiGet<{ plan_id: string; assets: PlanAsset[]; count: number }>(url);

export function useAssets(planId: string) {
  const { data, error, mutate, isLoading } = useSWR(
    planId ? `/plans/${planId}/assets` : null,
    assetFetcher,
    {
      refreshInterval: 10000, // Refresh every 10 seconds
    }
  );

  const [uploading, setUploading] = useState(false);

  const uploadAssets = useCallback(async (files: FileList | File[], epicRef?: string) => {
    if (!files.length) return;
    setUploading(true);
    try {
      const form = new FormData();
      for (let i = 0; i < files.length; i++) {
        form.append('files', files[i]);
      }
      if (epicRef) form.append('epic_ref', epicRef);

      const response = await fetch(`/api/plans/${planId}/assets`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }
      
      const result = await response.json();
      mutate(); // Refresh the list
      return result;
    } catch (err: unknown) {
      console.error('Upload error:', err);
      throw err;
    } finally {
      setUploading(false);
    }
  }, [planId, mutate]);

  const bindAsset = useCallback(async (filename: string, epicRef: string) => {
    await apiPost(`/plans/${planId}/assets/${encodeURIComponent(filename)}/bind`, { epic_ref: epicRef });
    mutate();
  }, [planId, mutate]);

  const unbindAsset = useCallback(async (filename: string, epicRef: string) => {
    await apiDelete(`/plans/${planId}/assets/${encodeURIComponent(filename)}/bind/${epicRef}`);
    mutate();
  }, [planId, mutate]);

  const updateAssetMeta = useCallback(async (filename: string, updates: Partial<PlanAsset>) => {
    await apiPatch(`/plans/${planId}/assets/${encodeURIComponent(filename)}`, updates);
    mutate();
  }, [planId, mutate]);

  return {
    assets: data?.assets || [],
    count: data?.count || 0,
    isLoading,
    isError: error,
    uploading,
    uploadAssets,
    bindAsset,
    unbindAsset,
    updateAssetMeta,
    refresh: mutate,
  };
}
