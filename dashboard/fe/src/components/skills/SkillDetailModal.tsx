'use client';

import React from 'react';
import { Skill, SkillCategory } from '@/types';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

interface SkillDetailModalProps {
  skill: Skill | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit?: (skill: Skill) => void;
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

export const SkillDetailModal: React.FC<SkillDetailModalProps> = ({
  skill,
  isOpen,
  onClose,
  onEdit,
}) => {
  if (!skill) return null;

  const catColor = categoryColors[skill.category] || 'var(--color-text-faint)';

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={skill.name}
      size="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-4 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-xs">history</span>
              Updated: {skill.updated_at || 'N/A'}
            </div>
            {skill.active_epics_count !== undefined && (
               <div className="flex items-center gap-1">
                 <span className="material-symbols-outlined text-xs text-blue-500">task_alt</span>
                 In {skill.active_epics_count} active Epics
               </div>
            )}
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-xs">analytics</span>
              Used {skill.usage_count} times
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onEdit && (
              <Button
                onClick={() => { onEdit(skill); onClose(); }}
                variant="outline"
                className="flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-base">edit</span>
                Edit Skill
              </Button>
            )}
          </div>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header Info */}
        <div className="flex items-center gap-3">
          <div 
            className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider text-white"
            style={{ background: catColor }}
          >
            {skill.category}
          </div>
          <span className="text-xs font-mono px-2 py-1 rounded bg-slate-100 text-slate-500">
            Version {skill.version}
          </span>
          {skill.is_draft && (
            <span className="text-xs font-bold px-2 py-1 rounded bg-amber-100 text-amber-600 border border-amber-200">
              DRAFT
            </span>
          )}
          {skill.trust_level === 'verified' && (
            <span className="flex items-center gap-1 text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded border border-blue-200">
              <span className="material-symbols-outlined text-[14px]">verified</span>
              Verified
            </span>
          )}
           {skill.trust_level === 'core' && (
            <span className="flex items-center gap-1 text-xs font-bold text-purple-600 bg-purple-50 px-2 py-1 rounded border border-purple-200">
              <span className="material-symbols-outlined text-[14px]">shield</span>
              Core
            </span>
          )}
        </div>

        {/* Description */}
        <section>
          <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
            Description
          </h4>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-main)' }}>
            {skill.description}
          </p>
        </section>

        {/* Roles & Tags */}
        <div className="grid grid-cols-2 gap-4">
          <section>
            <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
              Applicable Roles
            </h4>
            <div className="flex flex-wrap gap-2">
              {skill.applicable_roles.map((role) => (
                <span 
                  key={role}
                  className="px-2.5 py-1 rounded-full text-[10px] font-medium border border-border bg-surface"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {role}
                </span>
              ))}
            </div>
          </section>

          <section>
            <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
              Tags
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {skill.tags?.map((tag) => (
                <span 
                  key={tag}
                  className="px-2 py-0.5 rounded-sm text-[10px] font-medium bg-slate-50 text-slate-500 border border-slate-200"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </section>
        </div>

        {/* Action Source */}
        {skill.author && (
           <section>
             <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
               Author
             </h4>
             <div className="flex items-center gap-2 text-sm text-text-muted">
               <span className="material-symbols-outlined text-base">person</span>
               {skill.author}
             </div>
           </section>
        )}

        {/* Instruction Template */}
        {skill.instruction_template && (
          <section>
            <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
              Instruction Template
            </h4>
            <div className="p-4 rounded-lg bg-slate-900 text-slate-300 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap">
              {skill.instruction_template}
            </div>
          </section>
        )}

        {/* Version History / Changelog */}
        <section>
          <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
            Changelog
          </h4>
          <div className="border border-border rounded-lg overflow-hidden divide-y divide-border">
            {skill.changelog && skill.changelog.length > 0 ? (
              skill.changelog.map((log, i) => (
                <div key={i} className="p-3 bg-surface hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-text-main">v{log.version}</span>
                      {i === 0 && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-100 text-blue-600 font-bold uppercase tracking-tight">Latest</span>}
                    </div>
                    <span className="text-[10px] text-text-muted">
                      {new Date(log.date * 1000).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">
                    {log.changes}
                  </p>
                </div>
              ))
            ) : (
                <div className="p-3 bg-surface flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-text-main">v{skill.version}</span>
                    <span className="text-[10px] text-text-faint">Initial Version</span>
                  </div>
                  <span className="text-[10px] text-text-muted">{skill.updated_at || 'Recently'}</span>
                </div>
            )}
          </div>
        </section>
      </div>
    </Modal>
  );
};
