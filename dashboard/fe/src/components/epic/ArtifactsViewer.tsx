'use client';

import { useState } from 'react';
import { useArtifacts } from '@/hooks/use-war-room';

interface ArtifactsViewerProps {
  planId: string;
  epicRef: string;
}

const fileTypeIcons: Record<string, { icon: string; color: string }> = {
  txt: { icon: 'article', color: '#94a3b8' },
  md: { icon: 'description', color: '#3b82f6' },
  json: { icon: 'data_object', color: '#f59e0b' },
  log: { icon: 'terminal', color: '#10b981' },
  py: { icon: 'code', color: '#8b5cf6' },
  ts: { icon: 'code', color: '#3b82f6' },
  tsx: { icon: 'code', color: '#06b6d4' },
  js: { icon: 'javascript', color: '#f59e0b' },
  default: { icon: 'insert_drive_file', color: '#64748b' },
};

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return fileTypeIcons[ext] || fileTypeIcons.default;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ArtifactsViewer({ planId, epicRef }: ArtifactsViewerProps) {
  const { artifacts, isLoading, isError } = useArtifacts(planId, epicRef);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="p-4 animate-pulse space-y-3">
        <div className="h-4 w-24 bg-border/30 rounded" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-10 w-full bg-border/20 rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError || !artifacts || artifacts.length === 0) {
    return (
      <div className="p-4 text-center text-text-faint">
        <span className="material-symbols-outlined text-2xl mb-2 block">folder_open</span>
        <p className="text-xs">No artifacts found for this epic.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-surface-hover/30 flex items-center justify-between shrink-0">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">folder_special</span>
          Artifacts
        </h3>
        <span className="text-[10px] font-mono text-text-faint bg-surface-hover px-1.5 py-0.5 rounded">
          {artifacts.length} file{artifacts.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1.5">
        {artifacts.map((file) => {
          const icon = getFileIcon(file.name);
          const isSelected = selectedFile === file.name;

          return (
            <button
              key={file.name}
              onClick={() => setSelectedFile(isSelected ? null : file.name)}
              className={`w-full flex items-center gap-3 p-2.5 rounded-lg border transition-all text-left group ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/20'
                  : 'border-border bg-surface hover:border-text-faint hover:bg-surface-hover'
              }`}
            >
              {/* File icon */}
              <div 
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: `${icon.color}15` }}
              >
                <span className="material-symbols-outlined text-[18px]" style={{ color: icon.color }}>
                  {icon.icon}
                </span>
              </div>

              {/* File info */}
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-text-main truncate group-hover:text-primary transition-colors">
                  {file.name}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[9px] text-text-faint font-mono">
                    {formatFileSize(file.size)}
                  </span>
                  <span className="text-[9px] text-text-faint uppercase px-1 rounded bg-surface-hover border border-border/50">
                    {file.type || file.name.split('.').pop()}
                  </span>
                </div>
              </div>

              {/* Expand icon */}
              <span className={`material-symbols-outlined text-sm text-text-faint transition-transform ${
                isSelected ? 'rotate-180' : ''
              }`}>
                expand_more
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
