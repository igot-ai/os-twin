'use client';

import React, { useState, useMemo, useEffect } from 'react';
import useSWR from 'swr';
import { Skill, SkillCategory } from '@/types';
import { useSkills } from '@/hooks/use-skills';
import { SkillCard } from './SkillCard';
import { SkillDetailModal } from './SkillDetailModal';

const categoryColors: Record<SkillCategory, string> = {
  implementation: '#3b82f6',
  review: '#8b5cf6',
  testing: '#10b981',
  writing: '#f59e0b',
  analysis: '#06b6d4',
  compliance: '#ec4899',
  triage: '#ef4444',
};

type SortOption = 'name' | 'most-used' | 'recently-updated' | 'category';

export const SkillLibrary: React.FC = () => {
  const { skills, isLoading, isError } = useSkills();
  
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<SkillCategory[]>([]);
  const [sortOption, setSortOption] = useState<SortOption>('name');
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  
  // Local state for "attached" skills (since it's not in backend yet)
  // Using SWR for "local cache" persistence across session if needed
  const { data: attachedSkillIds, mutate: mutateAttached } = useSWR<string[]>('local:attached-skills', null, {
    fallbackData: [],
  });

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 200);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const toggleCategory = (category: SkillCategory) => {
    setSelectedCategories(prev => 
      prev.includes(category) 
        ? prev.filter(c => c !== category) 
        : [...prev, category]
    );
  };

  const toggleAttach = (id: string) => {
    const current = attachedSkillIds || [];
    const next = current.includes(id) 
      ? current.filter(i => i !== id) 
      : [...current, id];
    mutateAttached(next, false);
  };

  const filteredSkills = useMemo(() => {
    if (!skills) return [];

    return skills
      .filter(skill => {
        const matchesSearch = 
          skill.name.toLowerCase().includes(debouncedSearch.toLowerCase()) ||
          skill.description.toLowerCase().includes(debouncedSearch.toLowerCase());
        
        const matchesCategory = 
          selectedCategories.length === 0 || 
          selectedCategories.includes(skill.category);
        
        return matchesSearch && matchesCategory;
      })
      .sort((a, b) => {
        switch (sortOption) {
          case 'most-used':
            return b.usage_count - a.usage_count;
          case 'recently-updated':
            return (b.updated_at || '').localeCompare(a.updated_at || '');
          case 'category':
            return a.category.localeCompare(b.category);
          case 'name':
          default:
            return a.name.localeCompare(b.name);
        }
      });
  }, [skills, debouncedSearch, selectedCategories, sortOption]);

  if (isError) return <div className="p-8 text-red-500">Failed to load skills</div>;

  return (
    <div className="space-y-6">
      {/* Search + Filters */}
      <div className="flex flex-col md:flex-row md:items-center gap-4">
        <div 
          className="flex items-center gap-2 px-3 py-2 rounded-lg flex-1 max-w-sm"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-text-faint)' }}>search</span>
          <input
            type="text"
            placeholder="Search skills..."
            className="bg-transparent border-none outline-none text-xs w-full"
            style={{ color: 'var(--color-text-main)' }}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {Object.entries(categoryColors).map(([cat, color]) => {
            const isSelected = selectedCategories.includes(cat as SkillCategory);
            return (
              <button
                key={cat}
                onClick={() => toggleCategory(cat as SkillCategory)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium capitalize transition-all border ${
                  isSelected 
                    ? 'border-transparent text-white' 
                    : 'border-border text-text-muted hover:bg-slate-50'
                }`}
                style={{ 
                  background: isSelected ? color : 'transparent',
                  borderColor: isSelected ? 'transparent' : 'var(--color-border)'
                }}
              >
                {!isSelected && <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />}
                {cat}
              </button>
            );
          })}
          {selectedCategories.length > 0 && (
            <button 
              onClick={() => setSelectedCategories([])}
              className="px-2 py-1 text-[10px] text-blue-500 hover:underline"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 md:ml-auto">
          <select 
            className="bg-transparent text-[11px] font-medium border-border rounded px-2 py-1 outline-none"
            style={{ color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}
            value={sortOption}
            onChange={(e) => setSortOption(e.target.value as SortOption)}
          >
            <option value="name">Name A-Z</option>
            <option value="most-used">Most Used</option>
            <option value="recently-updated">Recently Updated</option>
            <option value="category">Category</option>
          </select>
          <div className="h-4 w-[1px] bg-border mx-1" />
          <span className="text-[11px] font-medium whitespace-nowrap" style={{ color: 'var(--color-text-faint)' }}>
            {filteredSkills.length} / {skills?.length || 0} skills
          </span>
          <div className="px-2 py-0.5 rounded bg-blue-50 text-blue-600 text-[10px] font-bold">
            {attachedSkillIds?.length || 0} Attached
          </div>
        </div>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-32 rounded-xl bg-slate-100 animate-pulse" />
          ))}
        </div>
      ) : filteredSkills.length > 0 ? (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
          {filteredSkills.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              isAttached={attachedSkillIds?.includes(skill.id)}
              onToggleAttach={toggleAttach}
              onClick={setSelectedSkill}
            />
          ))}
        </div>
      ) : (
        <div className="p-12 text-center border border-dashed border-border rounded-xl">
          <span className="material-symbols-outlined text-4xl mb-2" style={{ color: 'var(--color-text-faint)' }}>
            sentiment_dissatisfied
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>No skills found matching your filters</p>
        </div>
      )}

      {/* Modal */}
      <SkillDetailModal
        isOpen={!!selectedSkill}
        skill={selectedSkill}
        onClose={() => setSelectedSkill(null)}
        isAttached={selectedSkill ? attachedSkillIds?.includes(selectedSkill.id) : false}
        onToggleAttach={toggleAttach}
      />
    </div>
  );
};
