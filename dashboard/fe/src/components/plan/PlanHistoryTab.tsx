'use client';

import { useEffect } from 'react';
import { usePlanVersions } from '@/hooks/use-plan-versions';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { PlanVersion } from '@/types';

const SOURCE_BADGE: Record<string, { label: string; variant: 'primary' | 'secondary' | 'success' | 'warning' }> = {
  manual_save: { label: 'manual save', variant: 'primary' },
  ai_refine: { label: 'ai refine', variant: 'secondary' },
  expansion: { label: 'expansion', variant: 'success' },
  before_restore: { label: 'before restore', variant: 'warning' },
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
    versions,
    selectedVersion,
    isLoading,
    error,
    loadVersions,
    loadVersion,
    restoreVersion,
    clearSelection,
  } = usePlanVersions(planId);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  if (isLoading && versions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  if (error && versions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-6">
        <span className="material-symbols-outlined text-danger text-3xl mb-2">error</span>
        <p className="text-sm text-text-muted">{error}</p>
      </div>
    );
  }

  if (selectedVersion) {
    return <VersionDetail version={selectedVersion} onBack={clearSelection} onRestore={restoreVersion} isLoading={isLoading} />;
  }

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar">
      <div className="mb-6">
        <h2 className="text-sm font-bold text-text-main uppercase tracking-wider">Version History</h2>
        <p className="text-xs text-text-muted mt-1">
          Previous versions of this plan. Click to view, restore to revert.
        </p>
      </div>

      {versions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">history</span>
          <p className="text-sm text-text-muted">No versions yet. Versions are created when you save changes.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {versions.map((v) => (
            <VersionRow key={v.id} version={v} onClick={() => loadVersion(v.version)} />
          ))}
        </div>
      )}
    </div>
  );
}

function VersionRow({ version, onClick }: { version: PlanVersion; onClick: () => void }) {
  const badge = SOURCE_BADGE[version.change_source] || { label: version.change_source, variant: 'secondary' as const };

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 bg-surface border border-border rounded-lg p-3 hover:border-primary cursor-pointer transition-colors text-left"
    >
      <span className="font-semibold font-mono text-sm text-text-main min-w-[40px]">v{version.version}</span>
      <span className="text-sm text-text-muted truncate flex-1">{version.title}</span>
      <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
      <span className="text-xs text-text-faint font-mono whitespace-nowrap">{formatTimestamp(version.created_at)}</span>
    </button>
  );
}

function VersionDetail({
  version,
  onBack,
  onRestore,
  isLoading,
}: {
  version: PlanVersion;
  onBack: () => void;
  onRestore: (v: number) => Promise<string | null>;
  isLoading: boolean;
}) {
  const badge = SOURCE_BADGE[version.change_source] || { label: version.change_source, variant: 'secondary' as const };

  const handleRestore = async () => {
    await onRestore(version.version);
  };

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar flex flex-col">
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text-main transition-colors"
        >
          <span className="material-symbols-outlined text-[16px]">arrow_back</span>
          Back
        </button>
        <span className="font-mono text-sm font-semibold text-text-main">v{version.version}</span>
        <Badge variant={badge.variant} size="sm">{badge.label}</Badge>
        <span className="text-xs text-text-faint font-mono">{formatTimestamp(version.created_at)}</span>
        <div className="ml-auto">
          <Button variant="primary" size="sm" onClick={handleRestore} isLoading={isLoading}>
            Restore This Version
          </Button>
        </div>
      </div>

      <div className="flex-1 bg-background border border-border rounded-lg p-4 overflow-auto">
        <pre className="font-mono text-sm text-text-main whitespace-pre-wrap break-words">
          {version.content || '(no content)'}
        </pre>
      </div>
    </div>
  );
}
