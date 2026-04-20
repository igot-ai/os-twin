/**
 * SWR hooks for Knowledge query API.
 * 
 * Endpoint:
 * - POST /api/knowledge/namespaces/{namespace}/query -> QueryResultResponse
 */

import { useState, useCallback } from 'react';
import { apiPost } from '@/lib/api-client';

export interface QueryRequest {
  query: string;
  mode?: 'raw' | 'graph' | 'summarized';
  top_k?: number;
  threshold?: number;
  category?: string | null;
}

export interface ChunkHitResponse {
  text: string;
  score: number;
  file_path: string;
  filename: string;
  chunk_index: number;
  total_chunks: number;
  file_hash: string;
  mime_type: string | null;
  category_id: string | null;
  memory_links: string[];
}

export interface EntityHitResponse {
  id: string;
  name: string;
  label: string;
  score: number;
  description: string | null;
  category_id: string | null;
}

export interface CitationResponse {
  file: string;
  page: number | null;
  chunk_index: number;
  snippet_id: string;
}

export interface QueryResultResponse {
  query: string;
  mode: string;
  namespace: string;
  chunks: ChunkHitResponse[];
  entities: EntityHitResponse[];
  answer: string | null;
  citations: CitationResponse[];
  latency_ms: number;
  warnings: string[];
}

const KNOWLEDGE_BASE = '/api/knowledge';

/**
 * Hook to execute knowledge queries.
 * Uses manual state management since queries are POST requests triggered by user action.
 */
export function useKnowledgeQuery(namespace: string | null) {
  const [result, setResult] = useState<QueryResultResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const executeQuery = useCallback(async (request: QueryRequest): Promise<QueryResultResponse> => {
    if (!namespace) {
      throw new Error('Namespace is required');
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiPost<QueryResultResponse>(
        `${KNOWLEDGE_BASE}/namespaces/${namespace}/query`,
        {
          query: request.query,
          mode: request.mode || 'raw',
          top_k: request.top_k ?? 10,
          threshold: request.threshold ?? 0.5,
          category: request.category || null,
        }
      );
      setResult(response);
      return response;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [namespace]);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return {
    result,
    isLoading,
    error,
    executeQuery,
    clearResult,
  };
}
