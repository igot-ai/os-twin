'use client';

import React, { useState } from 'react';
import FileTree from './files/FileTree';
import FileViewer from './files/FileViewer';
import GitChangePanel from './files/GitChangePanel';

interface FileBrowserProps {
  planId: string;
}

export default function FileBrowser({ planId }: FileBrowserProps) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<'viewer' | 'git'>('viewer');

  const handleSelectFile = (path: string) => {
    setSelectedPath(path);
    setRightPanel('viewer');
  };

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* Left Sidebar: File Tree */}
      <aside className="w-[280px] border-r border-border bg-surface flex flex-col shrink-0 overflow-hidden shadow-sm">
        <div className="p-4 border-b border-border flex items-center justify-between bg-surface-hover/30 shrink-0">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-primary">folder</span>
            <span className="text-xs font-bold text-text-main uppercase tracking-widest">Files</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setRightPanel('git')}
              className={`p-1.5 rounded-lg transition-all flex items-center justify-center group ${
                rightPanel === 'git'
                  ? 'bg-primary text-white shadow-md'
                  : 'text-text-faint hover:bg-surface-hover hover:text-text-main'
              }`}
              title="View Git Changes"
            >
              <span className="material-symbols-outlined text-[16px] transition-colors group-hover:scale-110">history</span>
            </button>
            <button
              onClick={() => setSelectedPath(null)}
              className="p-1.5 rounded-lg transition-all flex items-center justify-center text-text-faint hover:bg-surface-hover hover:text-text-main group"
              title="Close File"
            >
              <span className="material-symbols-outlined text-[16px] group-hover:rotate-90 transition-transform">close</span>
            </button>
          </div>
        </div>
        <FileTree
          planId={planId}
          onSelectFile={handleSelectFile}
          selectedPath={selectedPath}
        />
      </aside>

      {/* Main Content: Viewer or Git Panel */}
      <main className="flex-1 flex flex-col overflow-hidden bg-background relative">
        {rightPanel === 'viewer' ? (
          <FileViewer planId={planId} path={selectedPath} />
        ) : (
          <GitChangePanel planId={planId} />
        )}
        
        {/* View Mode Toggle (Floating over viewer) */}
        {selectedPath && (
           <div className="absolute top-4 right-4 flex items-center gap-1 bg-surface/80 backdrop-blur-md p-1 rounded-xl border border-border shadow-2xl z-10 transition-all hover:bg-surface">
             <button
                onClick={() => setRightPanel('viewer')}
                className={`p-2 rounded-lg transition-all flex items-center justify-center group ${
                  rightPanel === 'viewer'
                    ? 'bg-primary text-white shadow-lg'
                    : 'text-text-faint hover:bg-surface-hover hover:text-text-main'
                }`}
                title="File Content"
             >
               <span className="material-symbols-outlined text-[18px]">description</span>
             </button>
             <button
                onClick={() => setRightPanel('git')}
                className={`p-2 rounded-lg transition-all flex items-center justify-center group ${
                  rightPanel === 'git'
                    ? 'bg-primary text-white shadow-lg'
                    : 'text-text-faint hover:bg-surface-hover hover:text-text-main'
                }`}
                title="Git History"
             >
               <span className="material-symbols-outlined text-[18px]">history</span>
             </button>
           </div>
        )}
      </main>
    </div>
  );
}
