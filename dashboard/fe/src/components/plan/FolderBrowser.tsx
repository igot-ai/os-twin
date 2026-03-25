'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';

interface DirEntry {
  name: string;
  path: string;
  has_children: boolean;
}

interface BrowseResult {
  current: string;
  parent: string | null;
  dirs: DirEntry[];
}

interface FolderBrowserProps {
  selectedPath: string;
  onSelectPath: (path: string) => void;
}

export default function FolderBrowser({ selectedPath, onSelectPath }: FolderBrowserProps) {
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const browse = useCallback(async (path?: string) => {
    setError(null);
    try {
      const url = path
        ? '/fs/browse?path=' + encodeURIComponent(path)
        : '/fs/browse';
      const data = await apiGet<BrowseResult>(url);
      setBrowseResult(data);
      onSelectPath(data.current);
    } catch {
      setError('Failed to browse directory');
    }
  }, [onSelectPath]);

  useEffect(() => {
    browse();
  }, [browse]);

  const pathSegments = browseResult?.current.split('/').filter(Boolean) ?? [];

  return (
    <div className="rounded-lg border border-border bg-background overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-border text-sm font-mono text-text-faint overflow-x-auto whitespace-nowrap">
        <span
          className="text-primary hover:underline cursor-pointer shrink-0"
          onClick={() => browse('/')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>home</span>
        </span>
        {pathSegments.map((part, i) => {
          const accPath = '/' + pathSegments.slice(0, i + 1).join('/');
          const isLast = i === pathSegments.length - 1;
          return (
            <span key={accPath} className="flex items-center gap-1">
              <span className="text-text-faint mx-0.5">/</span>
              {isLast ? (
                <span className="text-text-main font-medium">{part}</span>
              ) : (
                <span
                  className="text-primary hover:underline cursor-pointer"
                  onClick={() => browse(accPath)}
                >
                  {part}
                </span>
              )}
            </span>
          );
        })}
      </div>

      {/* Directory listing */}
      <div className="max-h-[200px] overflow-y-auto custom-scrollbar">
        {error && (
          <div className="p-4 text-center text-sm text-red-400">{error}</div>
        )}

        {!error && browseResult?.parent && (
          <div
            onClick={() => browse(browseResult.parent!)}
            className="flex items-center gap-2 px-3 py-2 hover:bg-surface-hover cursor-pointer font-mono text-sm text-text-muted"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>folder</span>
            <span>..</span>
          </div>
        )}

        {!error && browseResult?.dirs.length === 0 && (
          <div className="p-4 text-center text-sm text-text-faint">
            No subdirectories
          </div>
        )}

        {!error && browseResult?.dirs.map((d) => (
          <div
            key={d.path}
            onClick={() => browse(d.path)}
            className="flex items-center gap-2 px-3 py-2 hover:bg-surface-hover cursor-pointer font-mono text-sm text-text-main"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>folder</span>
            <span className="flex-1 truncate">{d.name}</span>
            {d.has_children && (
              <span className="text-text-faint text-xs ml-auto">›</span>
            )}
          </div>
        ))}
      </div>

      {/* Selected path footer */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-border bg-surface">
        <span className="text-text-faint text-xs font-mono">Selected:</span>
        <span className="text-primary text-sm font-mono flex-1 truncate">
          {selectedPath}
        </span>
      </div>
    </div>
  );
}
