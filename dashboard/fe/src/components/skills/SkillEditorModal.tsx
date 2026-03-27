'use client';

import React, { useState, useEffect } from 'react';
import { Skill, SkillCategory } from '@/types';
import { useSkillValidation } from '@/hooks/use-skills';

interface SkillEditorModalProps {
  skill?: Skill | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (skill: Partial<Skill>) => Promise<void>;
  onUpdate?: (name: string, skill: Partial<Skill>) => Promise<void>;
  onDelete?: (name: string) => Promise<void>;
}

export const SkillEditorModal: React.FC<SkillEditorModalProps> = ({
  skill,
  isOpen,
  onClose,
  onSave,
  onUpdate,
  onDelete,
}) => {
  const [name, setName] = useState(skill?.name || '');
  const [description, setDescription] = useState(skill?.description || '');
  const [category, setCategory] = useState<SkillCategory>(skill?.category || 'implementation');
  const [content, setContent] = useState(skill?.content || '');
  const [tags, setTags] = useState(skill?.tags?.join(', ') || '');
  const [trustLevel, setTrustLevel] = useState<string>(skill?.trust_level || 'experimental');
  const [applicableRolesInput, setApplicableRolesInput] = useState(skill?.applicable_roles?.join(', ') || '');
  const [isSaving, setIsSaving] = useState(false);
  const [validation, setValidation] = useState<{valid: boolean, errors: string[], warnings: string[]} | null>(null);

  const { validateSkill } = useSkillValidation();

  useEffect(() => {
    if (skill) {
      setName(skill.name);
      setDescription(skill.description);
      setCategory(skill.category);
      setContent(skill.content || '');
      setTags(skill.tags?.join(', ') || '');
      setTrustLevel(skill.trust_level || 'experimental');
      setApplicableRolesInput(skill.applicable_roles?.join(', ') || '');
    } else {
      setName('');
      setDescription('');
      setCategory('implementation');
      setContent('');
      setTags('');
      setTrustLevel('experimental');
      setApplicableRolesInput('');
    }
  }, [skill, isOpen]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (content.length > 10) {
        const res = await validateSkill(content);
        setValidation(res);
      } else {
        setValidation(null);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [content]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const skillData = {
        name,
        description,
        category,
        content,
        tags: tags.split(',').map(t => t.trim()).filter(Boolean),
        trust_level: trustLevel as Skill['trust_level'],
        applicable_roles: applicableRolesInput.split(',').map(r => r.trim()).filter(Boolean),
      };
      if (skill && onUpdate) {
        await onUpdate(skill.name, skillData);
      } else {
        await onSave(skillData);
      }
      onClose();
    } catch (e) {
      alert('Failed to save skill');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!skill || !onDelete) return;
    if (!confirm(`Delete skill "${skill.name}"? This cannot be undone.`)) return;
    setIsSaving(true);
    try {
      await onDelete(skill.name);
      onClose();
    } catch (e) {
      alert('Failed to delete skill');
    } finally {
      setIsSaving(false);
    }
  };

  const renderContentWithHighlights = () => {
    // Basic highlighting for {{variable}}
    const parts = content.split(/(\{\{[^}]*\}\})/g);
    return parts.map((part, i) => {
      if (part.startsWith('{{') && part.endsWith('}}')) {
        return <span key={i} className="bg-yellow-100 text-yellow-800 rounded px-1 font-mono">{part}</span>;
      }
      return part;
    });
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 animate-in fade-in duration-300">
      <div
        className="rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-300"
        style={{ background: 'var(--color-surface)' }}
      >
        {/* Header */}
        <div className="px-6 py-5 border-b flex items-center justify-between" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-xl text-primary">extension</span>
            </div>
            <div>
              <h2 className="text-lg font-extrabold" style={{ color: 'var(--color-text-main)' }}>{skill ? 'Edit Skill' : 'New Skill'}</h2>
              <p className="text-[11px] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>Define reusable instruction templates for roles</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-text-muted)' }}>close</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-7 custom-scrollbar">
          {/* Section: Identity */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">01</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Identity</h3>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Skill Name</label>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full p-3 rounded-xl border bg-white text-sm font-semibold transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                  style={{ borderColor: 'var(--color-border)' }}
                  placeholder="e.g. write-unit-tests"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value as SkillCategory)}
                  className="w-full p-3 rounded-xl border bg-white text-sm font-semibold transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <option value="implementation">Implementation</option>
                  <option value="review">Review</option>
                  <option value="testing">Testing</option>
                  <option value="writing">Writing</option>
                  <option value="analysis">Analysis</option>
                  <option value="compliance">Compliance</option>
                  <option value="triage">Triage</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Trust Level</label>
                <select
                  value={trustLevel}
                  onChange={e => setTrustLevel(e.target.value)}
                  className="w-full p-3 rounded-xl border bg-white text-sm font-semibold transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <option value="experimental">Experimental</option>
                  <option value="verified">Verified</option>
                  <option value="core">Core</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Description</label>
              <input
                value={description}
                onChange={e => setDescription(e.target.value)}
                className="w-full p-3 rounded-xl border bg-white text-sm transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                style={{ borderColor: 'var(--color-border)' }}
                placeholder="Brief overview of what this skill does"
              />
            </div>
          </div>

          {/* Section: Scope */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">02</span>
              <h3 className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Scope & Tags</h3>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Tags</label>
                <input
                  value={tags}
                  onChange={e => setTags(e.target.value)}
                  className="w-full p-3 rounded-xl border bg-white text-sm transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                  style={{ borderColor: 'var(--color-border)' }}
                  placeholder="python, testing, backend"
                />
                <p className="text-[10px] px-1" style={{ color: 'var(--color-text-faint)' }}>Comma separated</p>
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold uppercase tracking-wider px-1" style={{ color: 'var(--color-text-muted)' }}>Applicable Roles</label>
                <input
                  value={applicableRolesInput}
                  onChange={e => setApplicableRolesInput(e.target.value)}
                  className="w-full p-3 rounded-xl border bg-white text-sm transition-all focus:ring-4 focus:ring-primary/10 focus:outline-none"
                  style={{ borderColor: 'var(--color-border)' }}
                  placeholder="developer, reviewer, analyst"
                />
                <p className="text-[10px] px-1" style={{ color: 'var(--color-text-faint)' }}>Leave empty to allow all roles</p>
              </div>
            </div>
          </div>

          {/* Section: Template */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px]">03</span>
                <h3 className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-text-faint)' }}>Instruction Template</h3>
              </div>
              {validation && (
                <div className="flex gap-2">
                  {validation.errors.length > 0 && (
                    <span className="text-[10px] bg-red-50 text-red-600 px-2 py-0.5 rounded-full flex items-center gap-1 font-bold">
                      <span className="material-symbols-outlined text-[12px]">error</span>
                      {validation.errors.length} Errors
                    </span>
                  )}
                  {validation.warnings.length > 0 && (
                    <span className="text-[10px] bg-yellow-50 text-yellow-600 px-2 py-0.5 rounded-full flex items-center gap-1 font-bold">
                      <span className="material-symbols-outlined text-[12px]">warning</span>
                      {validation.warnings.length} Warnings
                    </span>
                  )}
                  {validation.valid && validation.errors.length === 0 && (
                    <span className="text-[10px] bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full flex items-center gap-1 font-bold">
                      <span className="material-symbols-outlined text-[12px]">check_circle</span>
                      Valid
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="relative border rounded-xl overflow-hidden min-h-[250px] flex flex-col bg-white" style={{ borderColor: 'var(--color-border)' }}>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                className="w-full flex-1 p-4 font-mono text-xs outline-none resize-none bg-transparent relative z-10 text-transparent caret-black focus:ring-4 focus:ring-primary/10"
                placeholder="Write your skill instructions here... Use {{variable}} for dynamic content."
              />
              <div className="absolute inset-0 p-4 font-mono text-xs pointer-events-none whitespace-pre-wrap break-words overflow-y-auto" style={{ color: 'var(--color-text-main)' }}>
                {renderContentWithHighlights()}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 px-1">
              {['task_description', 'guidelines', 'output_format', 'context'].map(v => (
                <span key={v} className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-primary/5 text-primary/70 border border-primary/10">{`{{${v}}}`}</span>
              ))}
            </div>

            {validation && validation.errors.map((err, i) => (
              <div key={i} className="text-xs text-red-600 flex items-center gap-1.5 bg-red-50 p-3 rounded-xl font-medium">
                <span className="material-symbols-outlined text-sm">error</span>
                {err}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div
          className="px-6 py-4 border-t flex items-center justify-between shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.06)]"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        >
          <div>
            {skill && onDelete && (
              <button
                onClick={handleDelete}
                className="px-4 py-2 text-sm font-bold text-red-500 hover:text-red-700 hover:bg-red-50 rounded-xl transition-all"
              >
                Delete Skill
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl border text-sm font-bold hover:bg-slate-50 transition-all"
              style={{ color: 'var(--color-text-main)', borderColor: 'var(--color-border)' }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || !name || !content || !!(validation && !validation.valid)}
              className="px-6 py-2.5 rounded-xl text-sm font-extrabold text-white shadow-lg shadow-primary/20 transition-all hover:brightness-105 active:scale-95 disabled:opacity-50 disabled:hover:brightness-100 disabled:active:scale-100 flex items-center gap-2"
              style={{ background: 'var(--color-primary)' }}
            >
              {isSaving && <span className="material-symbols-outlined text-base animate-spin">refresh</span>}
              {isSaving ? 'Saving...' : skill ? 'Update Skill' : 'Create Skill'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
