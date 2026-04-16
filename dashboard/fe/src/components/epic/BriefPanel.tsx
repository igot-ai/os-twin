'use client';


import { useBrief } from '@/hooks/use-war-room';

interface BriefPanelProps {
  planId: string;
  epicRef: string;
}

export default function BriefPanel({ planId, epicRef }: BriefPanelProps) {
  const { brief, isLoading, isError } = useBrief(planId, epicRef);

  if (isLoading) {
    return (
      <div className="p-4 animate-pulse space-y-3">
        <div className="h-4 w-32 bg-border/30 rounded" />
        <div className="h-3 w-full bg-border/20 rounded" />
        <div className="h-3 w-3/4 bg-border/20 rounded" />
        <div className="h-3 w-5/6 bg-border/20 rounded" />
      </div>
    );
  }

  if (isError || !brief) {
    return (
      <div className="p-4 text-center text-text-faint">
        <span className="material-symbols-outlined text-2xl mb-2 block">description</span>
        <p className="text-xs">No brief available for this epic.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-surface-hover/30 flex items-center justify-between shrink-0">
        <h3 className="text-[10px] font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">description</span>
          Brief
        </h3>
        <div className="flex items-center gap-2 text-[9px] text-text-faint">
          <span className="material-symbols-outlined text-[12px]">schedule</span>
          {new Date(brief.created_at).toLocaleDateString()}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
        {/* Markdown-rendered content */}
        <div className="prose prose-xs max-w-none text-text-main">
          {brief.content.split('\n').map((line, idx) => {
            // Simple markdown rendering
            if (line.startsWith('# ')) {
              return <h1 key={idx} className="text-lg font-black text-text-main mt-4 mb-2">{line.slice(2)}</h1>;
            }
            if (line.startsWith('## ')) {
              return <h2 key={idx} className="text-sm font-bold text-text-main mt-3 mb-1.5 border-b border-border pb-1">{line.slice(3)}</h2>;
            }
            if (line.startsWith('### ')) {
              return <h3 key={idx} className="text-xs font-bold text-text-main mt-2 mb-1">{line.slice(4)}</h3>;
            }
            if (line.match(/^\d+\.\s/)) {
              return (
                <div key={idx} className="flex gap-2 py-0.5 pl-2 text-xs text-text-muted">
                  <span className="text-primary font-bold shrink-0">{line.match(/^\d+/)?.[0]}.</span>
                  <span>{line.replace(/^\d+\.\s/, '')}</span>
                </div>
              );
            }
            if (line.startsWith('- ')) {
              return (
                <div key={idx} className="flex gap-2 py-0.5 pl-2 text-xs text-text-muted">
                  <span className="text-primary shrink-0">•</span>
                  <span>{line.slice(2)}</span>
                </div>
              );
            }
            if (line.trim() === '') return <div key={idx} className="h-2" />;
            return <p key={idx} className="text-xs text-text-muted leading-relaxed">{line}</p>;
          })}
        </div>

        {/* Working Directory Info */}
        {brief.working_dir && (
          <div className="mt-4 p-3 rounded-lg bg-surface-alt border border-border">
            <div className="text-[9px] font-bold text-text-faint uppercase tracking-wider mb-1">Working Directory</div>
            <code className="text-[10px] font-mono text-text-main break-all">{brief.working_dir}</code>
          </div>
        )}
      </div>
    </div>
  );
}
