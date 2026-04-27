'use client';

import React from 'react';
import { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';

/* ── Helpers ───────────────────────────────────────────────────────── */

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

/* ── Props ─────────────────────────────────────────────────────────── */

interface NamespaceOverviewProps {
  namespace: NamespaceMetaResponse;
  onNavigateImport: () => void;
  onNavigateQuery: () => void;
  onDelete: () => void;
  onRefresh: () => void;
}

/* ── Stat Card ─────────────────────────────────────────────────────── */

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: string;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div
      className="rounded-xl border p-3 flex items-start gap-3"
      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
    >
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: `${color}15` }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 18, color }}>
          {icon}
        </span>
      </div>
      <div>
        <p className="text-[11px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </p>
        <p className="text-lg font-bold leading-tight" style={{ color: 'var(--color-text-main)' }}>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
      </div>
    </div>
  );
}

/* ── Quick Action ──────────────────────────────────────────────────── */

function QuickAction({
  icon,
  label,
  description,
  onClick,
  variant = 'default',
}: {
  icon: string;
  label: string;
  description: string;
  onClick: () => void;
  variant?: 'default' | 'danger';
}) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 p-3 rounded-xl border text-left
        transition-all duration-150
        ${variant === 'danger'
          ? 'hover:bg-danger/5 hover:border-danger/30'
          : 'hover:bg-primary/5 hover:border-primary/30'
        }
      `}
      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
    >
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
        style={{
          background: variant === 'danger' ? 'var(--color-danger-muted)' : 'var(--color-primary-muted)',
        }}
      >
        <span
          className="material-symbols-outlined"
          style={{
            fontSize: 18,
            color: variant === 'danger' ? 'var(--color-danger)' : 'var(--color-primary)',
          }}
        >
          {icon}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p
          className="text-xs font-semibold"
          style={{
            color: variant === 'danger' ? 'var(--color-danger)' : 'var(--color-text-main)',
          }}
        >
          {label}
        </p>
        <p className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
          {description}
        </p>
      </div>
      <span
        className="material-symbols-outlined shrink-0"
        style={{ fontSize: 16, color: 'var(--color-text-faint)' }}
      >
        chevron_right
      </span>
    </button>
  );
}

/* ── Import Record Row ─────────────────────────────────────────────── */

function ImportRow({ imp }: { imp: NamespaceMetaResponse['imports'][number] }) {
  const statusColors: Record<string, string> = {
    running: 'var(--color-primary)',
    completed: 'var(--color-success)',
    failed: 'var(--color-danger)',
    interrupted: 'var(--color-warning)',
  };

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded-lg"
      style={{ background: 'var(--color-surface-hover)' }}
    >
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: statusColors[imp.status] || 'var(--color-text-muted)' }}
      />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium truncate" style={{ color: 'var(--color-text-main)' }}>
          {imp.folder_path.split('/').pop() || imp.folder_path}
        </p>
        <p className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
          {imp.file_count} files · {formatRelativeTime(imp.started_at)}
        </p>
      </div>
      <span
        className="text-[10px] font-medium uppercase tracking-wide"
        style={{ color: statusColors[imp.status] || 'var(--color-text-muted)' }}
      >
        {imp.status}
      </span>
    </div>
  );
}

/* ── Main Component ────────────────────────────────────────────────── */

export default function NamespaceOverview({
  namespace: ns,
  onNavigateImport,
  onNavigateQuery,
  onDelete,
  onRefresh,
}: NamespaceOverviewProps) {
  const { stats } = ns;
  const hasContent = stats.files_indexed > 0 || stats.chunks > 0;
  const recentImports = ns.imports.slice(0, 3);

  return (
    <div className="h-full overflow-y-auto p-5" style={{ scrollbarWidth: 'thin' }}>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h2
              className="text-xl font-bold truncate"
              style={{ color: 'var(--color-text-main)' }}
            >
              {ns.name}
            </h2>
            <span
              className="px-2 py-0.5 rounded-md text-[10px] font-medium uppercase tracking-wide"
              style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
            >
              {ns.language}
            </span>
          </div>
          {ns.description && (
            <p className="text-sm mb-2" style={{ color: 'var(--color-text-muted)' }}>
              {ns.description}
            </p>
          )}
          <div className="flex items-center gap-4 text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
            <span>Created {formatDate(ns.created_at)}</span>
            <span>·</span>
            <span>Updated {formatRelativeTime(ns.updated_at)}</span>
          </div>
        </div>
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg hover:bg-surface-hover transition-colors shrink-0"
          aria-label="Refresh namespace"
          title="Refresh"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--color-text-muted)' }}>
            refresh
          </span>
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard icon="description" label="Files" value={stats.files_indexed} color="#3B82F6" />
        <StatCard icon="dataset" label="Chunks" value={stats.chunks} color="#8B5CF6" />
        <StatCard icon="hub" label="Entities" value={stats.entities} color="#EC4899" />
        <StatCard icon="hard_drive" label="Storage" value={formatBytes(stats.bytes_on_disk)} color="#14B8A6" />
      </div>

      {/* Quick actions */}
      <div className="mb-6">
        <h3 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-text-muted)' }}>
          Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <QuickAction
            icon="upload"
            label="Import Documents"
            description={hasContent ? 'Add more files to this namespace' : 'Get started by importing files'}
            onClick={onNavigateImport}
          />
          <QuickAction
            icon="search"
            label="Query Knowledge"
            description={hasContent ? `Search across ${stats.chunks} chunks` : 'Import documents first'}
            onClick={onNavigateQuery}
          />
          <QuickAction
            icon="delete"
            label="Delete Namespace"
            description="Permanently remove all data"
            onClick={onDelete}
            variant="danger"
          />
        </div>
      </div>

      {/* Recent imports */}
      {recentImports.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-text-muted)' }}>
            Recent Imports
          </h3>
          <div className="space-y-1.5">
            {recentImports.map((imp, i) => (
              <ImportRow key={imp.job_id || i} imp={imp} />
            ))}
          </div>
        </div>
      )}

      {/* Configuration */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: 'var(--color-text-muted)' }}>
          Configuration
        </h3>
        <div
          className="rounded-xl border p-4 space-y-2"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        >
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--color-text-muted)' }}>Embedding Model</span>
            <span className="font-medium font-mono text-[11px]" style={{ color: 'var(--color-text-main)' }}>
              {ns.embedding_model}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--color-text-muted)' }}>Embedding Dimension</span>
            <span className="font-medium font-mono text-[11px]" style={{ color: 'var(--color-text-main)' }}>
              {ns.embedding_dimension}
            </span>
          </div>
          {ns.retention && (
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: 'var(--color-text-muted)' }}>Retention</span>
              <span className="font-medium text-[11px]" style={{ color: 'var(--color-text-main)' }}>
                {ns.retention.policy === 'ttl_days'
                  ? `${ns.retention.ttl_days} days`
                  : 'Manual'}
              </span>
            </div>
          )}
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--color-text-muted)' }}>Vectors</span>
            <span className="font-medium font-mono text-[11px]" style={{ color: 'var(--color-text-main)' }}>
              {stats.vectors.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: 'var(--color-text-muted)' }}>Relations</span>
            <span className="font-medium font-mono text-[11px]" style={{ color: 'var(--color-text-main)' }}>
              {stats.relations.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Empty state nudge */}
      {!hasContent && (
        <div
          className="mt-6 rounded-xl border-2 border-dashed p-6 text-center"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <span
            className="material-symbols-outlined text-[32px] mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            upload_file
          </span>
          <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-main)' }}>
            This namespace is empty
          </p>
          <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
            Import a folder of documents to populate the knowledge graph.
          </p>
          <button
            onClick={onNavigateImport}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>upload</span>
            Import Documents
          </button>
        </div>
      )}
    </div>
  );
}
