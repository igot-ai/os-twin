'use client';

import { useState, useCallback } from 'react';
import { ChangeEvent } from '@/types';
import { apiGet } from '@/lib/api-client';

export function usePlanChanges(planId: string) {
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [selectedChange, setSelectedChange] = useState<ChangeEvent | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChanges = useCallback(async () => {
    if (!planId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ changes: ChangeEvent[] }>(`/plans/${planId}/changes`);
      setChanges(data.changes || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load changes';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [planId]);

  const loadDiff = useCallback(async (changeId: string, filePath?: string) => {
    if (!planId) return;
    setIsLoading(true);
    setDiff(null);
    try {
      const url = `/plans/${planId}/changes/${changeId}/diff${filePath ? `?file_path=${encodeURIComponent(filePath)}` : ''}`;
      const data = await apiGet<{ diff: string }>(url);
      setDiff(data.diff || '');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load diff';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [planId]);

  const selectChange = useCallback((change: ChangeEvent | null) => {
    setSelectedChange(change);
    if (change) {
      loadDiff(change.id);
    } else {
      setDiff(null);
    }
  }, [loadDiff]);

  return {
    changes,
    selectedChange,
    diff,
    isLoading,
    error,
    loadChanges,
    loadDiff,
    selectChange,
  };
}
