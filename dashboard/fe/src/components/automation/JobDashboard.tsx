'use client';

import React from 'react';
import { useScheduler } from '@/hooks/use-scheduler';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/IconButton';

export function JobDashboard() {
  const { jobs, isLoading, isError, triggerJob, deleteJob, refresh } = useScheduler();

  if (isLoading) {
    return <div className="p-8 text-center text-text-muted">Loading automation jobs...</div>;
  }

  if (isError) {
    return <div className="p-8 text-center text-danger">Error loading jobs. Please try again.</div>;
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="p-12 border-2 border-dashed border-border rounded-xl text-center">
        <span className="material-symbols-outlined text-4xl text-text-faint mb-4">schedule</span>
        <h3 className="text-lg font-bold text-text-main mb-2">No Scheduled Jobs</h3>
        <p className="text-sm text-text-muted max-w-md mx-auto mb-6">
          You haven't created any automated data workflows yet. Create a job to start synchronizing your data on a schedule.
        </p>
      </div>
    );
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {jobs.map((job) => (
          <div 
            key={job.job_id} 
            className="p-5 bg-surface border border-border rounded-xl shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start mb-4">
              <div className="space-y-1">
                <h3 className="font-bold text-text-main leading-tight">{job.name}</h3>
                <div className="flex items-center gap-2">
                  <Badge variant={job.enabled ? "success" : "muted"}>
                    {job.enabled ? "Active" : "Disabled"}
                  </Badge>
                  <span className="text-[11px] text-text-muted font-medium">
                    Every {formatInterval(job.interval_seconds)}
                  </span>
                </div>
              </div>
              <div className="flex gap-1">
                <IconButton 
                  icon="play_arrow" 
                  size="sm" 
                  variant="ghost" 
                  onClick={() => triggerJob(job.job_id)}
                  title="Trigger Now"
                />
                <IconButton 
                  icon="delete" 
                  size="sm" 
                  variant="ghost" 
                  className="text-danger hover:bg-danger-light"
                  onClick={() => {
                    if (confirm(`Delete job "${job.name}"?`)) {
                      deleteJob(job.job_id);
                    }
                  }}
                  title="Delete Job"
                />
              </div>
            </div>

            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Type:</span>
                <span className="font-mono bg-surface-hover px-1.5 py-0.5 rounded text-text-main border border-border/50">
                  {job.task_type}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">Last Run:</span>
                <span className="text-text-main italic">
                  {job.last_run ? new Date(job.last_run).toLocaleString() : 'Never'}
                </span>
              </div>
            </div>

            {Object.keys(job.task_params).length > 0 && (
              <div className="p-2 bg-surface-hover rounded-lg border border-border/50 overflow-hidden">
                <div className="text-[10px] uppercase tracking-wider font-bold text-text-faint mb-1">Parameters</div>
                <pre className="text-[11px] text-text-muted overflow-x-auto custom-scrollbar whitespace-pre-wrap">
                  {JSON.stringify(job.task_params, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
