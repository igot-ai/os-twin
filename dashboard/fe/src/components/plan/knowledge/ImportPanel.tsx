'use client';

import React, { useState, useCallback } from 'react';
import { JobStatusResponse } from '@/hooks/use-knowledge-import';

interface ImportPanelProps {
  selectedNamespace: string | null;
  jobs: JobStatusResponse[];
  activeJob: JobStatusResponse | undefined;
  isLoading: boolean;
  onStartImport: (folderPath: string, options?: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch {
    return isoString;
  }
}

function JobCard({ job, isLatest }: { job: JobStatusResponse; isLatest: boolean }) {
  const progress = job.progress_total > 0 
    ? Math.round((job.progress_current / job.progress_total) * 100) 
    : 0;

  const stateColors: Record<string, string> = {
    pending: 'var(--color-text-muted)',
    running: 'var(--color-primary)',
    completed: 'var(--color-success)',
    failed: 'var(--color-danger)',
    interrupted: 'var(--color-warning)',
    cancelled: 'var(--color-text-muted)',
  };

  const stateLabels: Record<string, string> = {
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed',
    interrupted: 'Interrupted',
    cancelled: 'Cancelled',
  };

  return (
    <div 
      className={`rounded-xl border p-4 ${isLatest ? 'ring-2 ring-primary/20' : ''}`}
      style={{ 
        background: 'var(--color-surface-hover)', 
        borderColor: 'var(--color-border)' 
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span 
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: stateColors[job.state] }}
          />
          <span 
            className="text-xs font-semibold uppercase tracking-wide"
            style={{ color: stateColors[job.state] }}
          >
            {stateLabels[job.state]}
          </span>
        </div>
        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {job.operation}
        </span>
      </div>

      {/* Message */}
      {job.message && (
        <p className="text-sm mb-3" style={{ color: 'var(--color-text-main)' }}>
          {job.message}
        </p>
      )}

      {/* Progress bar (for running jobs) */}
      {job.state === 'running' && job.progress_total > 0 && (
        <div className="mb-3">
          <div className="flex justify-between text-[10px] mb-1">
            <span style={{ color: 'var(--color-text-muted)' }}>Progress</span>
            <span style={{ color: 'var(--color-text-main)' }}>
              {job.progress_current} / {job.progress_total} ({progress}%)
            </span>
          </div>
          <div 
            className="h-1.5 rounded-full overflow-hidden"
            style={{ background: 'var(--color-border)' }}
          >
            <div 
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: 'var(--color-primary)' }}
            />
          </div>
        </div>
      )}

      {/* Timestamps */}
      <div className="flex items-center gap-4 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">schedule</span>
          <span>Submitted: {formatTimestamp(job.submitted_at)}</span>
        </div>
        {job.finished_at && (
          <div className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[12px]">check_circle</span>
            <span>Finished: {formatTimestamp(job.finished_at)}</span>
          </div>
        )}
      </div>

      {/* Errors */}
      {job.errors.length > 0 && (
        <div 
          className="mt-3 p-2 rounded-lg text-xs"
          style={{ background: 'var(--color-danger-muted)', color: 'var(--color-danger)' }}
        >
          <p className="font-semibold mb-1">Errors ({job.errors.length})</p>
          <ul className="list-disc list-inside space-y-0.5">
            {job.errors.slice(0, 3).map((err, i) => (
              <li key={i} className="truncate">{err}</li>
            ))}
            {job.errors.length > 3 && (
              <li className="italic">+{job.errors.length - 3} more errors</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ImportPanel({
  selectedNamespace,
  jobs,
  activeJob,
  isLoading,
  onStartImport,
  onRefresh,
}: ImportPanelProps) {
  const [folderPath, setFolderPath] = useState('');
  const [chunkSize, setChunkSize] = useState(512);
  const [overlap, setOverlap] = useState(50);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showOptions, setShowOptions] = useState(false);

  const handleImport = useCallback(async () => {
    if (!folderPath.trim()) return;
    
    setIsSubmitting(true);
    try {
      await onStartImport(folderPath.trim(), {
        chunk_size: chunkSize,
        overlap,
      });
      setFolderPath('');
    } finally {
      setIsSubmitting(false);
    }
  }, [folderPath, chunkSize, overlap, onStartImport]);

  if (!selectedNamespace) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <span 
            className="material-symbols-outlined text-[48px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            folder_open
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            Select a Namespace
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Choose a namespace from the Namespaces tab to start importing files.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4" style={{ scrollbarWidth: 'thin' }}>
      {/* Import form */}
      <div 
        className="rounded-xl border p-4 mb-4"
        style={{ 
          background: 'var(--color-surface)', 
          borderColor: 'var(--color-border)' 
        }}
      >
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-main)' }}>
          Import Folder
        </h3>

        <div className="space-y-3">
          {/* Folder path input */}
          <div>
            <label 
              className="block text-xs font-medium mb-1.5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Folder Path *
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                placeholder="/absolute/path/to/folder"
                className="flex-1 px-3 py-2 rounded-lg border text-sm"
                style={{ 
                  background: 'var(--color-background)', 
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-main)'
                }}
              />
              <button
                onClick={handleImport}
                disabled={isSubmitting || !folderPath.trim() || !!activeJob}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {isSubmitting ? 'progress_activity' : 'upload'}
                </span>
                {isSubmitting ? 'Importing...' : 'Import'}
              </button>
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
              Enter an absolute path to a folder on the server
            </p>
          </div>

          {/* Options toggle */}
          <button
            onClick={() => setShowOptions(!showOptions)}
            className="flex items-center gap-1 text-xs font-medium transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined text-[16px]">
              {showOptions ? 'expand_less' : 'expand_more'}
            </span>
            Import Options
          </button>

          {/* Options panel */}
          {showOptions && (
            <div 
              className="p-3 rounded-lg space-y-3"
              style={{ background: 'var(--color-background)' }}
            >
              <div>
                <label 
                  className="block text-xs font-medium mb-1"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Chunk Size: {chunkSize}
                </label>
                <input
                  type="range"
                  min={128}
                  max={2048}
                  step={128}
                  value={chunkSize}
                  onChange={(e) => setChunkSize(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label 
                  className="block text-xs font-medium mb-1"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Overlap: {overlap}
                </label>
                <input
                  type="range"
                  min={0}
                  max={256}
                  step={16}
                  value={overlap}
                  onChange={(e) => setOverlap(Number(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </div>

        {/* Active job warning */}
        {activeJob && (
          <div 
            className="mt-3 p-2 rounded-lg text-xs flex items-center gap-2"
            style={{ 
              background: 'var(--color-warning-muted)', 
              color: 'var(--color-warning)' 
            }}
          >
            <span className="material-symbols-outlined text-[16px]">info</span>
            An import job is already running. Wait for it to complete before starting a new one.
          </div>
        )}
      </div>

      {/* Jobs list */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-main)' }}>
          Import Jobs
        </h3>
        <button
          onClick={onRefresh}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-surface-hover"
          style={{ color: 'var(--color-text-muted)' }}
          aria-label="Refresh jobs"
        >
          <span className="material-symbols-outlined text-[16px]">refresh</span>
          Refresh
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-8">
          <span 
            className="material-symbols-outlined text-[32px] mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            history
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No import jobs yet. Import a folder to see job history.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job, i) => (
            <JobCard key={job.job_id} job={job} isLatest={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
