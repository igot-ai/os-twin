'use client';

import { useEffect } from 'react';
import { usePlanChanges } from '@/hooks/use-plan-changes';
import { usePlanVersions } from '@/hooks/use-plan-versions';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { ChangeEvent } from '@/types';

const SOURCE_BADGE: Record<string, { label: string; variant: 'primary' | 'secondary' | 'success' | 'warning' | 'muted' }> = {
  manual_save: { label: 'manual save', variant: 'primary' },
  ai_refine: { label: 'ai refine', variant: 'secondary' },
  expansion: { label: 'expansion', variant: 'success' },
  before_restore: { label: 'before restore', variant: 'warning' },
  git: { label: 'git', variant: 'muted' },
};

function formatTimestamp(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString();
}

interface PlanHistoryTabProps {
  planId: string;
}

export default function PlanHistoryTab({ planId }: PlanHistoryTabProps) {
  const {
    changes,
    selectedChange,
    diff,
    isLoading,
    error: _error,
    loadChanges,
    selectChange,
  } = usePlanChanges(planId);

  const { restoreVersion } = usePlanVersions(planId);

  useEffect(() => {
    loadChanges();
  }, [loadChanges]);

  const handleRestore = async () => {
    if (selectedChange && selectedChange.type === 'plan_version' && selectedChange.version) {
      await restoreVersion(selectedChange.version);
      selectChange(null);
      loadChanges();
    }
  };

  if (isLoading && changes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar">
      <div className="mb-6">
        <h2 className="text-sm font-bold text-text-main uppercase tracking-wider">Plan History & Asset Changes</h2>
        <p className="text-xs text-text-muted mt-1">
          Unified timeline of plan versions and asset mutations (git).
        </p>
      </div>

      {changes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">history</span>
          <p className="text-sm text-text-muted">No history found for this plan.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {changes.map((change) => (
            <ChangeRow key={change.id} change={change} onClick={() => selectChange(change)} />
          ))}
        </div>
      )}

      {selectedChange && (
        <Modal
          isOpen={!!selectedChange}
          onClose={() => selectChange(null)}
          title={
            selectedChange.type === 'plan_version' 
              ? `Plan Version v${selectedChange.version}` 
              : selectedChange.is_uncommitted 
                ? 'Uncommitted Changes'
                : `Commit ${selectedChange.id?.substring(0, 7)}`
          }
          size="lg"
          footer={
            selectedChange.type === 'plan_version' ? (
              <div className="flex justify-end gap-2 w-full">
                <Button variant="outline" size="sm" onClick={() => selectChange(null)}>Cancel</Button>
                <Button variant="primary" size="sm" onClick={handleRestore} isLoading={isLoading}>
                  Restore This Version
                </Button>
              </div>
            ) : null
          }
        >
          <div className="flex flex-col h-[70vh]">
            <div className="mb-4 px-1">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant={selectedChange.type === 'plan_version' ? 'primary' : 'secondary'}>
                  {selectedChange.type === 'plan_version' ? 'Plan Content' : 'Asset Mutation'}
                </Badge>
                <span className="text-xs text-text-muted font-mono">{formatTimestamp(selectedChange.timestamp)}</span>
              </div>
              <p className="text-sm font-semibold text-text-main">
                {selectedChange.type === 'plan_version' ? selectedChange.title : selectedChange.message}
              </p>
              {selectedChange.author && <p className="text-xs text-text-muted mt-1">By: {selectedChange.author}</p>}
            </div>
            
            <div className="flex-1 bg-background border border-border rounded-lg overflow-hidden flex flex-col">
              <div className="bg-surface px-3 py-1.5 border-b border-border flex justify-between items-center">
                <span className="text-[10px] font-bold text-text-faint uppercase tracking-widest">Diff Preview</span>
                {selectedChange.files && selectedChange.files.length > 0 && (
                  <span className="text-[10px] text-text-muted">{selectedChange.files.length} files changed</span>
                )}
              </div>
              <div className="flex-1 overflow-auto p-4 custom-scrollbar bg-[#0d1117]">
                {isLoading && !diff ? (
                  <div className="flex items-center justify-center h-full">
                    <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
                  </div>
                ) : (
                  <DiffView diff={diff || ''} />
                )}
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ChangeRow({ change, onClick }: { change: ChangeEvent; onClick: () => void }) {
  const isVersion = change.type === 'plan_version';
  const icon = isVersion ? 'description' : 'commit';
  const source = isVersion ? change.change_source || 'zvec' : change.source || 'git';
  const badge = SOURCE_BADGE[source] || { label: source, variant: 'secondary' as const };

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 bg-surface border border-border rounded-lg p-3 hover:border-primary cursor-pointer transition-colors text-left group"
    >
      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isVersion ? 'bg-primary/10 text-primary' : 'bg-info/10 text-info'}`}>
        <span className="material-symbols-outlined text-[18px]">{icon}</span>
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          {isVersion ? (
            <span className="font-bold font-mono text-sm text-text-main">v{change.version}</span>
          ) : (
            <span className="font-mono text-[11px] text-text-faint uppercase">{change.id?.substring(0, 7)}</span>
          )}
          <span className="text-sm text-text-main truncate font-medium">
            {isVersion ? change.title : change.message}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
          {change.author && <span className="text-[10px] text-text-faint">@{change.author}</span>}
          {!isVersion && change.files && change.files.length > 0 && (
            <span className="text-[10px] text-text-muted">{change.files[0]}{change.files.length > 1 ? ` + ${change.files.length - 1} more` : ''}</span>
          )}
        </div>
      </div>
      
      <div className="text-right flex flex-col items-end gap-1">
        <span className="text-[10px] text-text-faint font-mono whitespace-nowrap">{formatTimestamp(change.timestamp)}</span>
        <span className="material-symbols-outlined text-[16px] text-text-faint group-hover:text-primary transition-colors">chevron_right</span>
      </div>
    </button>
  );
}

function DiffView({ diff }: { diff: string }) {
  if (!diff) return <div className="text-xs text-text-muted font-mono p-2">No changes detected.</div>;

  const lines = diff.split('\n');
  return (
    <div className="font-mono text-[11px] leading-5 w-full">
      {lines.map((line, i) => {
        let bgColor = 'transparent';
        let textColor = '#c9d1d9';
        
        if (line.startsWith('+') && !line.startsWith('+++')) {
          bgColor = 'rgba(46, 160, 67, 0.15)';
          textColor = '#7ee787';
        } else if (line.startsWith('-') && !line.startsWith('---')) {
          bgColor = 'rgba(248, 81, 73, 0.15)';
          textColor = '#ffa198';
        } else if (line.startsWith('@@')) {
          bgColor = 'rgba(56, 139, 253, 0.1)';
          textColor = '#79c0ff';
        } else if (line.startsWith('diff') || line.startsWith('index') || line.startsWith('---') || line.startsWith('+++')) {
          textColor = '#8b949e';
          bgColor = 'rgba(110, 118, 129, 0.1)';
        }

        return (
          <div key={i} className="flex px-2 group" style={{ backgroundColor: bgColor }}>
            <span className="w-10 select-none text-right pr-3 opacity-30 text-[10px] border-r border-border/10 mr-3">
              {i + 1}
            </span>
            <span className="flex-1 whitespace-pre-wrap" style={{ color: textColor }}>
              {line || ' '}
            </span>
          </div>
        );
      })}
    </div>
  );
}
