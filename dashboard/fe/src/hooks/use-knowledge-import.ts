/**
 * SWR hooks for Knowledge import/jobs API.
 * 
 * Endpoints:
 * - POST /api/knowledge/namespaces/{namespace}/import -> ImportFolderResponse
 * - GET /api/knowledge/namespaces/{namespace}/jobs -> NamespaceJobsResponse
 * - GET /api/knowledge/namespaces/{namespace}/jobs/{job_id} -> JobStatusResponse
 */

import useSWR from 'swr';
import { apiGet, apiPost } from '@/lib/api-client';

export interface ImportFolderRequest {
  folder_path: string;
  options?: {
    chunk_size?: number;
    overlap?: number;
    [key: string]: unknown;
  };
}

export interface ImportFolderResponse {
  job_id: string;
  namespace: string;
}

export interface JobStatusResponse {
  job_id: string;
  namespace: string;
  operation: string;
  state: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted' | 'cancelled';
  submitted_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress_current: number;
  progress_total: number;
  message: string;
  errors: string[];
  result: Record<string, unknown> | null;
}

export interface GraphCountsResponse {
  entities: number;
  chunks: number;
  relations: number;
}

export interface NamespaceJobsResponse {
  jobs: JobStatusResponse[];
  graph_counts: GraphCountsResponse;
}

const KNOWLEDGE_BASE = '/knowledge';

/**
 * Hook to fetch all jobs for a namespace (with live graph counts).
 */
export function useKnowledgeJobs(namespace: string | null) {
  const { data, error, mutate, isLoading } = useSWR<NamespaceJobsResponse>(
    namespace ? `${KNOWLEDGE_BASE}/namespaces/${namespace}/jobs` : null,
    {
      revalidateOnFocus: false,
      dedupingInterval: 2000,
    }
  );

  return {
    jobs: data?.jobs,
    graphCounts: data?.graph_counts ?? { entities: 0, chunks: 0, relations: 0 },
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook to fetch a single job status.
 * Automatically polls while job is running (every 2s).
 */
export function useKnowledgeJob(namespace: string | null, jobId: string | null) {
  const isTerminalState = (state: string) => 
    ['completed', 'failed', 'interrupted', 'cancelled'].includes(state);

  const { data, error, mutate, isLoading } = useSWR<JobStatusResponse>(
    namespace && jobId ? `${KNOWLEDGE_BASE}/namespaces/${namespace}/jobs/${jobId}` : null,
    {
      revalidateOnFocus: false,
      // Poll every 2 seconds while job is running
      refreshInterval: (data) => {
        if (data && !isTerminalState(data.state)) {
          return 2000;
        }
        return 0;
      },
      dedupingInterval: 1000,
    }
  );

  return {
    job: data,
    isLoading,
    isError: error,
    isTerminal: data ? isTerminalState(data.state) : false,
    refresh: mutate,
  };
}

/**
 * Hook to trigger an import operation.
 */
export function useKnowledgeImport() {
  const startImport = async (
    namespace: string,
    request: ImportFolderRequest
  ): Promise<ImportFolderResponse> => {
    return apiPost<ImportFolderResponse>(
      `${KNOWLEDGE_BASE}/namespaces/${namespace}/import`,
      request
    );
  };

  return {
    startImport,
  };
}

/**
 * Combined hook for import panel - handles import trigger and job monitoring.
 */
export function useKnowledgeImportMonitor(namespace: string | null) {
  const { jobs, graphCounts, isLoading: jobsLoading, refresh: refreshJobs } = useKnowledgeJobs(namespace);
  const { startImport } = useKnowledgeImport();

  // Get the most recent running/pending job
  const activeJob = jobs?.find(j => 
    ['pending', 'running'].includes(j.state)
  );

  // Get the most recent job (any state)
  const latestJob = jobs?.[0];

  return {
    jobs,
    graphCounts,
    activeJob,
    latestJob,
    isLoading: jobsLoading,
    startImport,
    refreshJobs,
  };
}

