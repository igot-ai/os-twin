'use client';

import React from 'react';
import { Skill, SkillCategory } from '@/types';

interface SkillCardProps {
  skill: Skill;
  isAttached?: boolean;
  onToggleAttach?: (id: string) => void;
  onClick?: (skill: Skill) => void;
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
  isAttached = false, 
  onToggleAttach,
  onClick 
}) => {
  const catColor = categoryColors[skill.category] || 'var(--color-text-faint)';

  return (
    <div
      className="p-4 rounded-xl border-l-[3px] border transition-all duration-200 fade-in-up cursor-pointer group"
      style={{
        borderLeftColor: catColor,
        borderTopColor: 'var(--color-border)',
        borderRightColor: 'var(--color-border)',
        borderBottomColor: 'var(--color-border)',
        background: 'var(--color-surface)',
        boxShadow: 'var(--shadow-card)',
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
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ color: 'var(--color-text-main)' }}>{skill.name}</span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded" style={{ background: '#f1f5f9', color: 'var(--color-text-faint)' }}>
            v{skill.version}
          </span>
          {skill.trust_level === 'verified' && (
            <span className="material-symbols-outlined text-[14px] text-blue-500" title="Verified Skill">verified</span>
          )}
          {skill.trust_level === 'core' && (
            <span className="material-symbols-outlined text-[14px] text-purple-500" title="Core Skill">shield</span>
          )}
        </div>
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onToggleAttach?.(skill.id ?? skill.name);
          }}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold transition-all ${
            isAttached 
              ? 'bg-green-50 text-green-600 border border-green-200' 
              : 'bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100'
          }`}
        >
          <span className="material-symbols-outlined text-[14px]">
            {isAttached ? 'check_circle' : 'add_circle'}
          </span>
          {isAttached ? 'Attached' : 'Attach'}
        </button>
      </div>

      {/* Description */}
      <p 
        className="text-[11px] leading-relaxed mb-4 line-clamp-2" 
        style={{ color: 'var(--color-text-muted)' }}
      >
        {skill.description}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-dashed" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center gap-1.5 flex-wrap">
          {skill.applicable_roles.map((role) => (
            <span 
              key={role} 
              className="px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-tight"
              style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}
            >
              {role}
            </span>
          ))}
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
