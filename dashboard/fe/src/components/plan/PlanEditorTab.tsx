'use client';

import { useState, useEffect } from 'react';
import { MarkdownPreview } from './MarkdownPreview';
import { StructuredPlanView } from './StructuredPlanView';

interface PlanEditorTabProps {
  content: string;
  onChange: (content: string) => void;
}

type ViewMode = 'edit' | 'preview' | 'split' | 'structured';

export default function PlanEditorTab({ content, onChange }: PlanEditorTabProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('structured');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        setViewMode('structured');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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
            Markdown Editor
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
          <button
            onClick={() => setViewMode('structured')}
            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2 ${
              viewMode === 'structured'
                ? 'bg-primary text-white shadow-sm'
                : 'text-text-muted hover:text-text-main hover:bg-surface-hover'
            }`}
            title="Epic Design View (Ctrl+Shift+S)"
          >
            <span className="material-symbols-outlined text-[16px]">account_tree</span>
            Epic Design
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
        
        {viewMode === 'preview' && (
          <div className="w-full h-full bg-background/30">
            <MarkdownPreview content={content} />
          </div>
        )}

        {viewMode === 'split' && (
          <div className="w-1/2 h-full bg-background/30">
            {/* When in split mode, decide between Structured and Preview based on context. 
                For now, split mode defaults to Preview, but we could add a toggle here.
                Let's stick with the request: "Split mode with structured: left = raw editor, right = structured view" */}
            <StructuredPlanView />
          </div>
        )}

        {viewMode === 'structured' && (
          <div className="w-full h-full bg-background/30">
            <StructuredPlanView />
          </div>
        )}
      </div>
    </div>
  );
}
