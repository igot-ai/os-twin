/**
 * SWR hooks for Knowledge graph API.
 * 
 * Endpoint:
 * - GET /api/knowledge/namespaces/{namespace}/graph?limit=200 -> GraphResponse
 */

import useSWR from 'swr';

export interface GraphNodeResponse {
  id: string;
  label: string;
  name: string;
  score: number;
  properties: Record<string, unknown>;
}

export interface GraphEdgeResponse {
  source: string;
  target: string;
  label: string;
}

export interface GraphStatsResponse {
  node_count: number;
  edge_count: number;
}

export interface GraphResponse {
  nodes: GraphNodeResponse[];
  edges: GraphEdgeResponse[];
  stats: GraphStatsResponse;
  error: string | null;
}

const KNOWLEDGE_BASE = '/knowledge';
const DEFAULT_LIMIT = 200;

/**
 * Hook to fetch the knowledge graph for a namespace.
 * Caps rendering at 200 nodes by default (configurable via limit param).
 */
export function useKnowledgeGraph(namespace: string | null, limit: number = DEFAULT_LIMIT) {
  const { data, error, mutate, isLoading } = useSWR<GraphResponse>(
    namespace ? `${KNOWLEDGE_BASE}/namespaces/${namespace}/graph?limit=${limit}` : null,
    {
      revalidateOnFocus: false,
      revalidateIfStale: true,
      dedupingInterval: 2000,    // Shorter dedup so namespace switches aren't stale
      revalidateOnMount: true,   // Always fetch on mount / key change
    }
  );

  return {
    graph: data,
    nodes: data?.nodes ?? [],
    edges: data?.edges ?? [],
    stats: data?.stats ?? { node_count: 0, edge_count: 0 },
    error: data?.error ?? (error ? String(error) : null),
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook to get a single entity by ID from the graph.
 */
export function useKnowledgeEntity(namespace: string | null, entityId: string | null) {
  const { nodes, isLoading, error } = useKnowledgeGraph(namespace);

  const entity = entityId 
    ? nodes.find(n => n.id === entityId) ?? null 
    : null;

  return {
    entity,
    isLoading,
    error,
  };
}
