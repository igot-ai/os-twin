'use client';

import useSWR from 'swr';

export interface AIRecentCall {
  type: 'completion' | 'embedding';
  model: string;
  purpose: string | null;
  caller: string | null;
  latency_ms: number;
  success: boolean;
  timestamp: number;
}

export interface AIStats {
  total_completions: number;
  total_embeddings: number;
  total_errors: number;
  completions_by_model: Record<string, number>;
  embeddings_by_model: Record<string, number>;
  completions_by_purpose: Record<string, number>;
  calls_by_caller: Record<string, number>;
  avg_completion_latency_ms: number;
  avg_embedding_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  recent_calls: AIRecentCall[];
}

export function useAIStats(refreshInterval = 5000) {
  const { data, error, isLoading, mutate } = useSWR<AIStats>(
    '/ai/stats',
    { refreshInterval },
  );

  return {
    stats: data,
    isLoading,
    isError: !!error,
    refresh: mutate,
  };
}
