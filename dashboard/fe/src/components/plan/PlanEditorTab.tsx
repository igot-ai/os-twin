'use client';

import React, { useState } from 'react';
import { MarkdownPreview } from './MarkdownPreview';

interface PlanEditorTabProps {
  content: string;
  onChange: (content: string) => void;
}

type ViewMode = 'edit' | 'preview' | 'split';

export default function PlanEditorTab({ content, onChange }: PlanEditorTabProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('edit');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-1 bg-background/50 p-1 rounded-lg border border-border">
          <button
            onClick={() => setViewMode('edit')}
            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2 ${
              viewMode === 'edit'
                ? 'bg-primary text-white shadow-sm'
                : 'text-text-muted hover:text-text-main hover:bg-surface-hover'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">edit</span>
            Edit
          </button>
          <button
            onClick={() => setViewMode('preview')}
            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2 ${
              viewMode === 'preview'
                ? 'bg-primary text-white shadow-sm'
                : 'text-text-muted hover:text-text-main hover:bg-surface-hover'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">visibility</span>
            Preview
          </button>
          <button
            onClick={() => setViewMode('split')}
            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2 ${
              viewMode === 'split'
                ? 'bg-primary text-white shadow-sm'
                : 'text-text-muted hover:text-text-main hover:bg-surface-hover'
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">vertical_split</span>
            Split
          </button>
        </div>
        
        <div className="text-[10px] font-bold text-text-faint uppercase tracking-widest">
          {viewMode} Mode
        </div>
      </div>

      {/* Editor/Preview Area */}
      <div className="flex-1 flex overflow-hidden">
        {(viewMode === 'edit' || viewMode === 'split') && (
          <textarea
            className={`h-full font-mono text-sm bg-background border-none resize-none p-4 focus:outline-none custom-scrollbar text-text-main placeholder:text-text-faint ${
              viewMode === 'split' ? 'w-1/2 border-r border-border' : 'w-full'
            }`}
            value={content}
            onChange={(e) => onChange(e.target.value)}
            placeholder={"# Plan: My Feature\n\n## Config\nworking_dir: .\n\n## EPIC-001 — Feature Title\n..."}
            spellCheck={false}
          />
        )}
        
        {(viewMode === 'preview' || viewMode === 'split') && (
          <div className={`${viewMode === 'split' ? 'w-1/2' : 'w-full'} h-full bg-background/30`}>
            <MarkdownPreview content={content} />
          </div>
        )}
      </div>
    </div>
  );
}
