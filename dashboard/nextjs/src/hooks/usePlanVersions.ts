'use client';

import { useState, useCallback } from 'react';
import { PlanVersion } from '@/types';
import { apiGet, apiPost } from '@/lib/api';

export function usePlanVersions(planId: string) {
  const [versions, setVersions] = useState<PlanVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<PlanVersion | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadVersions = useCallback(async () => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ versions: PlanVersion[]; count: number }>(
        `/api/plans/${planId}/versions`
      );
      setVersions(data.versions || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load versions';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [planId]);

  const loadVersion = useCallback(async (version: number) => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ version: PlanVersion }>(
        `/api/plans/${planId}/versions/${version}`
      );
      setSelectedVersion(data.version || null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load version';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [planId]);

  const restoreVersion = useCallback(async (version: number): Promise<string | null> => {
    if (!planId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiPost<{ status: string; restored_version: number }>(
        `/api/plans/${planId}/versions/${version}/restore`,
        {}
      );
      // Reload versions after restore
      await loadVersions();
      setSelectedVersion(null);
      return data.status === 'restored' ? null : 'Restore failed';
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to restore version';
      setError(msg);
      return msg;
    } finally {
      setIsLoading(false);
    }
  }, [planId, loadVersions]);

  const clearSelection = useCallback(() => {
    setSelectedVersion(null);
  }, []);

  return {
    versions,
    selectedVersion,
    isLoading,
    error,
    loadVersions,
    loadVersion,
    restoreVersion,
    clearSelection,
  };
}
