import useSWR from 'swr';
import { FileEntry, FileTreeNode, FileContentResponse, FileChanges } from '@/types';

/**
 * Hook to fetch the file tree for a plan (2 levels deep initially).
 */
export function useFileTree(planId: string | undefined) {
  const { data, error, isLoading, mutate } = useSWR<FileTreeNode[]>(
    planId ? `/plans/${planId}/files/tree` : null
  );

  return {
    tree: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook to fetch a flat list of files in a directory.
 */
export function useFileList(planId: string | undefined, path: string) {
  const { data, error, isLoading, mutate } = useSWR<FileEntry[]>(
    planId && path ? `/plans/${planId}/files?path=${encodeURIComponent(path)}` : null
  );

  return {
    entries: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook to fetch file content.
 */
export function useFileContent(planId: string | undefined, path: string | null) {
  const { data, error, isLoading, mutate } = useSWR<FileContentResponse>(
    planId && path ? `/plans/${planId}/files/content?path=${encodeURIComponent(path)}` : null,
    {
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  return {
    content: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}

/**
 * Hook to fetch git changes.
 */
export function useFileChanges(planId: string | undefined) {
  const { data, error, isLoading, mutate } = useSWR<FileChanges>(
    planId ? `/plans/${planId}/files/changes` : null,
    {
      refreshInterval: 30000,
    }
  );

  return {
    changes: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
