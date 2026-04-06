'use client';

import React from 'react';
import { Skill, SkillCategory } from '@/types';
import { Button } from '@/components/ui/Button';

interface SkillCardProps {
  skill: Skill;
  onClick?: (skill: Skill) => void;
  onToggle?: (skill: Skill) => Promise<void> | void;
  isToggling?: boolean;
}

const categoryColors: Record<SkillCategory, string> = {
  implementation: '#3b82f6',
  review: '#8b5cf6',
  testing: '#10b981',
  writing: '#f59e0b',
  analysis: '#06b6d4',
  compliance: '#ec4899',
  triage: '#ef4444',
};

export const SkillCard: React.FC<SkillCardProps> = ({
  skill,
  onClick,
  onToggle,
  isToggling = false
}) => {
  const catColor = categoryColors[skill.category] || 'var(--color-text-faint)';
  const toggleLabel = isToggling
    ? (skill.enabled === false ? 'Enabling...' : 'Disabling...')
    : (skill.enabled === false ? 'Enable Skill' : 'Disable Skill');
  const toggleIcon = skill.enabled === false ? 'toggle_on' : 'toggle_off';

  return (
    <div
      className="p-4 rounded-xl border-l-[3px] border transition-all duration-200 fade-in-up cursor-pointer group flex flex-col"
      style={{
        borderLeftColor: skill.enabled === false ? 'var(--color-text-faint)' : catColor,
        borderTopColor: 'var(--color-border)',
        borderRightColor: 'var(--color-border)',
        borderBottomColor: 'var(--color-border)',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-card)',
        minHeight: '160px',
        opacity: skill.enabled === false ? 0.6 : 1
      }}
      onClick={() => onClick?.(skill)}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-card)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span
              className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded text-white"
              style={{ background: catColor }}
            >
              {skill.category}
            </span>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: '#f1f5f9', color: 'var(--color-text-faint)' }}>
              v{skill.version}
            </span>
            {skill.is_draft && (
              <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-600 border border-amber-200">
                DRAFT
              </span>
            )}
            {skill.enabled === false && (
              <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-600 border border-red-200">
                DISABLED
              </span>
            )}
            {skill.trust_level === 'verified' && (
              <span className="material-symbols-outlined text-[14px] text-blue-500" title="Verified Skill">verified</span>
            )}
            {skill.trust_level === 'core' && (
              <span className="material-symbols-outlined text-[14px] text-purple-500" title="Core Skill">shield</span>
            )}
          </div>
          <div className="text-sm font-bold break-words" style={{ color: 'var(--color-text-main)' }}>
            {skill.name}
          </div>
        </div>
        {onToggle && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={isToggling}
            className={`shrink-0 gap-1.5 rounded-full px-3 ${
              skill.enabled === false
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                : 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100'
            }`}
            onClick={(event) => {
              event.stopPropagation();
              void onToggle(skill);
            }}
            aria-label={toggleLabel}
            title={toggleLabel}
          >
            <span className="material-symbols-outlined text-sm">{toggleIcon}</span>
            {toggleLabel}
          </Button>
        )}
      </div>

      {/* Description */}
      <p 
        className="text-[11px] leading-relaxed mb-3 line-clamp-2" 
        style={{ color: 'var(--color-text-muted)' }}
      >
        {skill.description}
      </p>

      {/* Tags */}
      {skill.tags && skill.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {skill.tags.slice(0, 3).map(tag => (
            <span 
              key={tag} 
              className="text-[9px] px-1.5 py-0.5 rounded-sm bg-slate-50 border border-slate-100 text-slate-500"
            >
              #{tag}
            </span>
          ))}
          {skill.tags.length > 3 && (
            <span className="text-[9px] text-slate-400">+{skill.tags.length - 3}</span>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-dashed" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center gap-1.5 flex-wrap">
          {skill.applicable_roles.slice(0, 2).map((role) => (
            <span 
              key={role} 
              className="px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-tight"
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}
            >
              {role}
            </span>
          ))}
          {skill.applicable_roles.length > 2 && (
             <span className="text-[9px] text-slate-400">+{skill.applicable_roles.length - 2}</span>
          )}
        </div>
        <div className="flex items-center gap-1 text-[10px] font-medium" style={{ color: 'var(--color-text-faint)' }}>
          {skill.score && (
            <span className="mr-2 px-1 rounded bg-yellow-50 text-yellow-700 border border-yellow-200" title="Relevance Score">
              {Math.round(skill.score * 100)}%
            </span>
          )}
          {skill.author && (
             <span className="mr-2 flex items-center gap-0.5" title="Author">
               <span className="material-symbols-outlined text-[10px]">person</span>
               {skill.author}
             </span>
          )}
          <span className="material-symbols-outlined text-xs">analytics</span>
          {skill.usage_count}
        </div>
      </div>
    </div>
  );
};
