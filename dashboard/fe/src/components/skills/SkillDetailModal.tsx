'use client';

import React from 'react';
import { Skill, SkillCategory } from '@/types';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

interface SkillDetailModalProps {
  skill: Skill | null;
  isOpen: boolean;
  onClose: () => void;
  isAttached?: boolean;
  onToggleAttach?: (id: string) => void;
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
  isAttached = false,
  onToggleAttach,
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
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-xs">analytics</span>
              Used {skill.usage_count} times
            </div>
          </div>
          <Button
            onClick={() => onToggleAttach?.(skill.id)}
            variant={isAttached ? 'outline' : 'primary'}
            className="flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-base">
              {isAttached ? 'remove_circle' : 'add_circle'}
            </span>
            {isAttached ? 'Detach Skill' : 'Attach Skill'}
          </Button>
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

        {/* Roles */}
        <section>
          <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
            Applicable Roles
          </h4>
          <div className="flex flex-wrap gap-2">
            {skill.applicable_roles.map((role) => (
              <span 
                key={role}
                className="px-2.5 py-1 rounded-full text-xs font-medium border border-border bg-surface"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {role}
              </span>
            ))}
          </div>
        </section>

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

        {/* Version History Placeholder */}
        <section>
          <h4 className="text-[11px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--color-text-faint)' }}>
            Version History
          </h4>
          <div className="border border-border rounded-lg overflow-hidden">
            <div className="flex items-center justify-between p-3 bg-surface border-b border-border">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-text-main">v{skill.version}</span>
                <span className="text-[10px] text-text-faint">Current Version</span>
              </div>
              <span className="text-[10px] text-text-muted">{skill.updated_at || 'Recently'}</span>
            </div>
            {skill.forked_from && (
              <div className="flex items-center justify-between p-3 bg-surface/50">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-text-muted">v1.0 (Initial)</span>
                  <span className="text-[10px] text-text-faint px-1.5 py-0.5 rounded bg-slate-100">FORKED</span>
                </div>
                <span className="text-[10px] text-text-muted">Jan 2026</span>
              </div>
            )}
          </div>
        </section>
      </div>
    </Modal>
  );
};
