'use client';

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Plan, Domain, RoleSummary } from '@/types';
import ProgressRing from './ProgressRing';
import { Skeleton } from '../ui/Skeleton';
import { getRoleColor, getRoleInitials } from '@/lib/role-utils';
import ConfirmDialog from '../ui/ConfirmDialog';

const domainColors: Record<Domain, { bg: string; text: string; dot: string }> = {
  software: { bg: 'rgba(59, 130, 246, 0.08)', text: '#3b82f6', dot: '#3b82f6' },
  data: { bg: 'rgba(20, 184, 166, 0.08)', text: '#14b8a6', dot: '#14b8a6' },
  audit: { bg: 'rgba(245, 158, 11, 0.08)', text: '#f59e0b', dot: '#f59e0b' },
  compliance: { bg: 'rgba(139, 92, 246, 0.08)', text: '#8b5cf6', dot: '#8b5cf6' },
  custom: { bg: 'rgba(100, 116, 139, 0.08)', text: '#64748b', dot: '#64748b' },
};

function relativeTime(dateStr: string) {
  const now = new Date();
  const date = new Date(dateStr);
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function PlanCard({ plan, isFocused = false, onDelete }: { plan: Plan, isFocused?: boolean, onDelete?: (planId: string) => void }) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const dc = domainColors[plan.domain ?? 'custom'] || domainColors.custom;
  
  // Derive roles from distribution if backend roles are empty
  const roles: (RoleSummary & { count?: number })[] = plan.roles && plan.roles.length > 0 
    ? plan.roles 
    : Object.entries(plan.role_distribution || {}).map(([name, count]) => ({
        name,
        count,
        initials: getRoleInitials(name),
        color: getRoleColor(name)
      }));

  const criticalPath = plan.critical_path ?? { completed: 0, total: 0 };

  return (
    <Link
      href={`/plans/${plan.plan_id}`}
      className={`block p-4 rounded-xl border transition-all duration-200 group bg-surface shadow-card hover:shadow-card-hover hover:-translate-y-0.5 ${
        isFocused ? 'ring-2 ring-primary border-transparent scale-[1.02] shadow-lg' : 'border-border'
      }`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2.5">
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase"
          style={{ background: dc.bg, color: dc.text }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: dc.dot }} />
          {plan.domain ?? 'custom'}
        </span>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-text-faint">
            {plan.updated_at ? relativeTime(plan.updated_at) : '—'}
          </span>
          {onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-500/10 transition-all"
              title="Delete plan"
            >
              <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500 transition-colors" style={{ fontSize: 14 }}>delete</span>
            </button>
          )}
        </div>
      </div>

      {onDelete && showDeleteConfirm && (
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          onClose={() => setShowDeleteConfirm(false)}
          onConfirm={() => { onDelete(plan.plan_id); setShowDeleteConfirm(false); }}
          title="Delete Plan"
          message={`Are you sure you want to delete "${plan.title}"? This will permanently remove all plan files, war-rooms, and related data.`}
        />
      )}

      {/* Title */}
      <h3
        className="text-sm font-bold mb-1 line-clamp-2 group-hover:text-primary transition-colors text-text-main"
      >
        {plan.title}
      </h3>

      {/* Goal excerpt */}
      <p className="text-xs mb-3 line-clamp-1 text-text-muted">
        {plan.goal ?? ''}
      </p>

      {/* Metrics row */}
      <div className="flex items-center gap-3 mb-3">
        <ProgressRing value={plan.pct_complete ?? 0} size={36} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-text-main">
            {plan.completed_epics ?? 0}/{plan.epic_count ?? 0} EPICs
          </div>
          <div className="text-[10px] text-text-faint">
            CP: {criticalPath.completed}/{criticalPath.total}
          </div>
        </div>
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between pt-3 border-t border-border-light">
        {/* Role distribution chips */}
        <div className="flex items-center gap-1.5 overflow-hidden">
          {roles.slice(0, 3).map((role) => (
            <div
              key={role.name}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-background border border-border-light shrink-0"
              title={`${role.count || 1}x ${role.name}`}
            >
              <span className="text-[9px] font-bold text-text-main leading-none">
                {role.count || 1}×
              </span>
              <div
                className="w-3 h-3 rounded-full flex items-center justify-center text-[6px] font-extrabold text-white"
                style={{ background: role.color }}
              >
                {role.initials.substring(0, 1)}
              </div>
            </div>
          ))}
          {roles.length > 3 && (
            <span className="text-[9px] text-text-faint font-medium shrink-0">
              +{roles.length - 3}
            </span>
          )}
        </div>

        {/* Escalation indicator */}
        {(plan.escalations ?? 0) > 0 && (
          <div
            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-danger-light text-danger-text"
          >
            <span className="material-symbols-outlined text-xs" style={{ fontSize: 12 }}>warning</span>
            {plan.escalations ?? 0}
          </div>
        )}
      </div>
    </Link>
  );
}

export function PlanCardSkeleton() {
  return (
    <div className="block p-4 rounded-xl border border-border bg-surface shadow-card">
      <div className="flex items-center justify-between mb-2.5">
        <Skeleton className="h-4 w-16 rounded-full" />
        <Skeleton className="h-3 w-12" />
      </div>
      <Skeleton className="h-4 w-full mb-1" />
      <Skeleton className="h-4 w-3/4 mb-3" />
      <div className="flex items-center gap-3 mb-3">
        <Skeleton variant="circle" className="w-9 h-9" />
        <div className="flex-1">
          <Skeleton className="h-3 w-20 mb-1" />
          <Skeleton className="h-2 w-12" />
        </div>
      </div>
      <div className="flex items-center justify-between pt-3 border-t border-border-light">
        <div className="flex items-center -space-x-1.5">
          <Skeleton variant="circle" className="w-6 h-6 border-2 border-surface" />
          <Skeleton variant="circle" className="w-6 h-6 border-2 border-surface" />
          <Skeleton variant="circle" className="w-6 h-6 border-2 border-surface" />
        </div>
        <Skeleton className="h-4 w-8 rounded" />
      </div>
    </div>
  );
}

