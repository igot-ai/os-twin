'use client';

import React, { useState, useEffect } from 'react';
import { Skill, SkillCategory } from '@/types';
import { useSkillValidation } from '@/hooks/use-skills';

interface SkillEditorModalProps {
  skill?: Skill | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (skill: Partial<Skill>) => Promise<void>;
}

export const SkillEditorModal: React.FC<SkillEditorModalProps> = ({
  skill,
  isOpen,
  onClose,
  onSave
}) => {
  const [name, setName] = useState(skill?.name || '');
  const [description, setDescription] = useState(skill?.description || '');
  const [category, setCategory] = useState<SkillCategory>(skill?.category || 'implementation');
  const [content, setContent] = useState(skill?.content || '');
  const [tags, setTags] = useState(skill?.tags?.join(', ') || '');
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
    } else {
      setName('');
      setDescription('');
      setCategory('implementation');
      setContent('');
      setTags('');
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
      await onSave({
        name,
        description,
        category,
        content,
        tags: tags.split(',').map(t => t.trim()).filter(Boolean),
      });
      onClose();
    } catch (e) {
      alert('Failed to save skill');
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="p-6 border-b flex items-center justify-between">
          <h2 className="text-xl font-bold">{skill ? 'Edit Skill' : 'Create New Skill'}</h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase text-slate-500">Skill Name</label>
              <input 
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full p-2 rounded-lg border focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="e.g. write-unit-tests"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase text-slate-500">Category</label>
              <select 
                value={category}
                onChange={e => setCategory(e.target.value as SkillCategory)}
                className="w-full p-2 rounded-lg border focus:ring-2 focus:ring-blue-500 outline-none"
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
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase text-slate-500">Description</label>
            <input 
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full p-2 rounded-lg border focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="Brief overview of what this skill does"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase text-slate-500">Tags (comma separated)</label>
            <input 
              value={tags}
              onChange={e => setTags(e.target.value)}
              className="w-full p-2 rounded-lg border focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="python, testing, backend"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase text-slate-500">Instruction Template (Markdown)</label>
              {validation && (
                <div className="flex gap-2">
                  {validation.errors.length > 0 && (
                    <span className="text-[10px] bg-red-50 text-red-600 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px]">error</span>
                      {validation.errors.length} Errors
                    </span>
                  )}
                  {validation.warnings.length > 0 && (
                    <span className="text-[10px] bg-yellow-50 text-yellow-600 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px]">warning</span>
                      {validation.warnings.length} Warnings
                    </span>
                  )}
                  {validation.valid && validation.errors.length === 0 && (
                    <span className="text-[10px] bg-green-50 text-green-600 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px]">check_circle</span>
                      Valid
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="relative border rounded-xl overflow-hidden min-h-[300px] flex flex-col bg-slate-50">
              <textarea 
                value={content}
                onChange={e => setContent(e.target.value)}
                className="w-full flex-1 p-4 font-mono text-sm outline-none resize-none bg-transparent relative z-10 text-transparent caret-black"
                placeholder="Write your skill instructions here... Use {{variable}} for dynamic content."
              />
              <div className="absolute inset-0 p-4 font-mono text-sm pointer-events-none whitespace-pre-wrap break-words overflow-y-auto">
                {renderContentWithHighlights()}
              </div>
            </div>
            <div className="text-[10px] text-slate-400">
               Supports Markdown. Available variables: {"{{task_description}}, {{guidelines}}, {{output_format}}, {{context}}"}
            </div>
            
            {validation && validation.errors.map((err, i) => (
              <div key={i} className="text-xs text-red-500 flex items-center gap-1 bg-red-50 p-2 rounded">
                <span className="material-symbols-outlined text-sm">error</span>
                {err}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t bg-slate-50 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800">
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={isSaving || !name || !content || !!(validation && !validation.valid)}
            className="px-6 py-2 rounded-xl text-sm font-bold text-white shadow-lg shadow-blue-200 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:hover:scale-100"
            style={{ background: 'var(--color-primary)' }}
          >
            {isSaving ? 'Saving...' : skill ? 'Update Skill' : 'Create Skill'}
          </button>
        </div>
      </div>
    </div>
  );
};
