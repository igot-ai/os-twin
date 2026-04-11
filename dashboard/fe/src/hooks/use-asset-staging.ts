/**
 * useAssetStaging — Browser-side attachment staging buffer.
 *
 * Mirrors the same stage→flush pattern used by the Discord and Telegram bots.
 * Files are held in React state until a planId is available, then flushed
 * to the backend via POST /api/plans/{planId}/assets.
 */

import { useState, useCallback, useMemo } from 'react';

const MAX_STAGED_BYTES = 50 * 1024 * 1024; // 50 MB

export interface StagedFile {
  file: File;
  name: string;
  size: number;
  mimeType: string;
  stagedAt: number;
  epicRef?: string;
}

export interface UseAssetStagingReturn {
  /** Currently staged files. */
  stagedFiles: StagedFile[];
  /** Number of staged files. */
  stagedCount: number;
  /** Total bytes staged. */
  stagedSizeBytes: number;
  /** Whether any files are staged. */
  hasStagedFiles: boolean;
  /** Whether a flush is in progress. */
  isFlushing: boolean;
  /** Last error message (from rejection or flush failure). */
  lastError: string | null;

  /** Stage files into the buffer. */
  stageFiles: (files: File[], epicRef?: string) => void;
  /** Upload all staged files to a plan and clear the buffer. */
  flushTo: (planId: string) => Promise<void>;
  /** Discard all staged files. */
  clearStaged: () => void;
  /** Remove a specific staged file by index. */
  removeStaged: (index: number) => void;
}

export function useAssetStaging(): UseAssetStagingReturn {
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [isFlushing, setIsFlushing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const stagedCount = stagedFiles.length;
  const stagedSizeBytes = useMemo(
    () => stagedFiles.reduce((sum, f) => sum + f.size, 0),
    [stagedFiles],
  );
  const hasStagedFiles = stagedCount > 0;

  const stageFiles = useCallback((files: File[], epicRef?: string) => {
    setLastError(null);

    const newFiles: StagedFile[] = files.map((f) => ({
      file: f,
      name: f.name,
      size: f.size,
      mimeType: f.type || 'application/octet-stream',
      stagedAt: Date.now(),
      epicRef,
    }));

    setStagedFiles((prev) => {
      const totalSize = prev.reduce((s, f) => s + f.size, 0)
        + newFiles.reduce((s, f) => s + f.size, 0);

      if (totalSize > MAX_STAGED_BYTES) {
        setLastError(`Total size (${Math.round(totalSize / 1024 / 1024)}MB) exceeds the 50MB limit.`);
        return prev; // reject — don't add
      }

      return [...prev, ...newFiles];
    });
  }, []);

  const flushTo = useCallback(async (planId: string) => {
    if (stagedFiles.length === 0) return;

    setIsFlushing(true);
    setLastError(null);
    try {
      const form = new FormData();
      for (const sf of stagedFiles) {
        form.append('files', sf.file);
      }
      // Forward epicRef from first file if present
      const epicRef = stagedFiles.find((f) => f.epicRef)?.epicRef;
      if (epicRef) form.append('epic_ref', epicRef);

      const response = await fetch(`/api/plans/${planId}/assets`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setLastError(err.detail || `Upload failed (${response.status})`);
      }

      // Clear buffer regardless of success (files were sent)
      setStagedFiles([]);
    } catch (err: any) {
      setLastError(err.message || 'Upload failed');
      setStagedFiles([]); // still clear — files can't be retried reliably
    } finally {
      setIsFlushing(false);
    }
  }, [stagedFiles]);

  const clearStaged = useCallback(() => {
    setStagedFiles([]);
    setLastError(null);
  }, []);

  const removeStaged = useCallback((index: number) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  return {
    stagedFiles,
    stagedCount,
    stagedSizeBytes,
    hasStagedFiles,
    isFlushing,
    lastError,
    stageFiles,
    flushTo,
    clearStaged,
    removeStaged,
  };
}
