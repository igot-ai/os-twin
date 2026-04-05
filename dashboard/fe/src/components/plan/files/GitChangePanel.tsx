'use client';

import React from 'react';
import { useFileChanges } from '@/hooks/use-files';

interface GitChangePanelProps {
  planId: string;
}

export default function GitChangePanel({ planId }: GitChangePanelProps) {
  const { changes, isLoading, isError, refresh } = useFileChanges(planId);

  if (isLoading) return <div className="p-4 text-xs animate-pulse">Loading changes...</div>;
  if (isError) return <div className="p-4 text-xs text-danger font-bold">Error loading git changes</div>;
  if (!changes?.git_enabled) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-text-faint bg-background/30 rounded-xl border-2 border-dashed border-border m-4">
        <span className="material-symbols-outlined text-4xl mb-3">history</span>
        <p className="text-sm font-bold text-text-muted">Git Not Enabled</p>
        <p className="text-[11px] mt-2 leading-relaxed">This project is not a git repository. Git changes and history are unavailable.</p>
      </div>
    );
  }

  const parsedStatus = changes.status.map((line) => {
    const code = line.substring(0, 2);
    const path = line.substring(3).trim();
    return { code, path };
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-3 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0 mb-1">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-text-muted">commit</span>
          <h3 className="text-[11px] font-bold text-text-faint uppercase tracking-widest">Version Control</h3>
        </div>
        <button 
           onClick={() => refresh()}
           className="p-1.5 hover:bg-surface-hover rounded-full transition-colors group"
           title="Refresh Git Status"
        >
          <span className="material-symbols-outlined text-[16px] text-text-faint group-hover:text-primary transition-colors">sync</span>
        </button>
      </div>

      {/* Changes Section */}
      <div className="flex flex-col gap-2 flex-1 overflow-hidden">
        <div className="text-[10px] font-bold text-text-muted flex items-center justify-between px-1">
           <span>UNSTAGED CHANGES ({parsedStatus.length})</span>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar border border-border rounded-lg bg-surface/30">
          {parsedStatus.length === 0 ? (
            <div className="h-full flex items-center justify-center italic text-[11px] text-text-faint p-4 text-center">
              No pending changes
            </div>
          ) : (
            <div className="divide-y divide-border">
              {parsedStatus.map((s, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2 text-[11px] group hover:bg-surface-hover transition-colors">
                  <span className={`font-mono font-bold w-4 text-center ${getStatusColor(s.code)}`} title={s.code}>
                    {s.code.trim() || 'M'}
                  </span>
                  <span className="text-text-main truncate font-mono flex-1">{s.path}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Commit History Section */}
      <div className="flex flex-col gap-2 flex-1 overflow-hidden">
        <div className="text-[10px] font-bold text-text-muted flex items-center justify-between px-1">
           <span>RECENT COMMITS ({changes.recent_commits.length})</span>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar border border-border rounded-lg bg-surface/30">
          {changes.recent_commits.length === 0 ? (
            <div className="h-full flex items-center justify-center italic text-[11px] text-text-faint p-4 text-center">
              No commit history
            </div>
          ) : (
            <div className="divide-y divide-border">
              {changes.recent_commits.map((c, i) => (
                <div key={i} className="flex flex-col gap-1 p-3 group hover:bg-surface-hover transition-colors">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-text-main leading-snug line-clamp-1">{c.subject}</span>
                    <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded shrink-0">{c.hash}</span>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-text-faint font-medium">
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[12px]">person</span>
                      {c.author}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[12px]">schedule</span>
                      {new Date(c.timestamp * 1000).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getStatusColor(code: string): string {
  const c = code.trim();
  if (c === 'M') return 'text-amber-500';
  if (c === 'A') return 'text-success';
  if (c === 'D') return 'text-danger';
  if (c === '??') return 'text-primary';
  return 'text-text-muted';
}
