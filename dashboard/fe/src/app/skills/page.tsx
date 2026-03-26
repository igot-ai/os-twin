'use client';

import React, { useState } from 'react';
import { Skill } from '@/types';
import { apiPut, apiDelete } from '@/lib/api-client';
import { SkillLibrary } from '@/components/skills/SkillLibrary';
import { SkillEditorModal } from '@/components/skills/SkillEditorModal';
import { useSkills } from '@/hooks/use-skills';

export default function SkillsPage() {
  const { syncWithDisk, createSkill, refresh } = useSkills();
  const [isSyncing, setIsSyncing] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const res = await syncWithDisk();
      alert(`Synced ${res.synced_count} skills!`);
      refresh();
    } catch (e) {
      alert('Sync failed');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleCreate = async (skill: any) => {
    await createSkill(skill);
    refresh();
  };

  const handleUpdate = async (name: string, skill: Partial<Skill>) => {
    await apiPut(`/skills/${name}`, skill);
    refresh();
  };

  const handleDelete = async (name: string) => {
    await apiDelete(`/skills/${name}`);
    refresh();
  };

  const handleEdit = (skill: Skill) => {
    setEditingSkill(skill);
    setIsEditorOpen(true);
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto fade-in-up">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-extrabold" style={{ color: 'var(--color-text-main)' }}>Skill Library</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              Browse, search, and manage prompt-instruction packs for agent roles
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={handleSync}
              disabled={isSyncing}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50"
            >
              <span className={`material-symbols-outlined text-base ${isSyncing ? 'animate-spin' : ''}`}>sync</span>
              {isSyncing ? 'Syncing...' : 'Sync with Disk'}
            </button>
            <button
              onClick={() => { setEditingSkill(null); setIsEditorOpen(true); }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white" style={{ background: 'var(--color-primary)' }}>
              <span className="material-symbols-outlined text-base">add</span>
              Create Skill
            </button>
          </div>
        </div>

        {/* Skill Library Container */}
        <SkillLibrary onEdit={handleEdit} />

        {/* Editor Modal */}
        <SkillEditorModal
          isOpen={isEditorOpen}
          skill={editingSkill}
          onClose={() => { setIsEditorOpen(false); setEditingSkill(null); }}
          onSave={handleCreate}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
        />
      </div>
  );
}
