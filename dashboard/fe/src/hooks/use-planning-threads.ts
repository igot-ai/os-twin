import useSWR from 'swr';
import { PlanningThread } from '@/types';

interface ThreadsResponse {
  threads: PlanningThread[];
  total: number;
}

export function usePlanningThreads(limit = 20, offset = 0) {
  const { data, error, mutate, isLoading } = useSWR<ThreadsResponse>(
    `/plans/threads?limit=${limit}&offset=${offset}`,
    {
      refreshInterval: 0, // manual refresh only
    }
  );

  return {
    threads: data?.threads || [],
    total: data?.total || 0,
    isLoading,
    error,
    mutate
  };
}
