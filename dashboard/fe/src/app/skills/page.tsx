'use client';

import { SkillLibrary } from '@/components/skills/SkillLibrary';

export default function SkillsPage() {
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
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white" style={{ background: 'var(--color-primary)' }}>
            <span className="material-symbols-outlined text-base">add</span>
            Create Skill
          </button>
        </div>

        {/* Skill Library Container */}
        <SkillLibrary />
      </div>
  );
}
