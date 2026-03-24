'use client';

import { useState, useRef, useEffect } from 'react';
import useSWR from 'swr';
import { Skill } from '@/types';

const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface SkillChipInputProps {
  selectedSkillRefs: string[];
  onChange: (skillRefs: string[]) => void;
}

export default function SkillChipInput({ selectedSkillRefs, onChange }: SkillChipInputProps) {
  const { data: allSkills = [], isLoading } = useSWR<Skill[]>('/api/skills', fetcher);
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedSkills = allSkills.filter(s => selectedSkillRefs.includes(s.name));
  const availableSkills = allSkills.filter(s => 
    !selectedSkillRefs.includes(s.name) && 
    (s.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
     s.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleSkill = (skillName: string) => {
    if (selectedSkillRefs.includes(skillName)) {
      onChange(selectedSkillRefs.filter(ref => ref !== skillName));
    } else {
      onChange([...selectedSkillRefs, skillName]);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <div 
        className="flex flex-wrap gap-2 p-2 min-h-[44px] rounded-lg border transition-all cursor-text focus-within:ring-2 focus-within:ring-primary/20"
        style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        onClick={() => setIsOpen(true)}
      >
        {selectedSkills.map(skill => (
          <span 
            key={skill.id}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold animate-in zoom-in-95"
            style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
          >
            {skill.name}
            <button 
              type="button" 
              onClick={(e) => { e.stopPropagation(); toggleSkill(skill.name); }}
              className="hover:opacity-70"
            >
              <span className="material-symbols-outlined text-sm leading-none">close</span>
            </button>
          </span>
        ))}
        <input 
          type="text"
          className="flex-1 bg-transparent border-none outline-none text-xs min-w-[120px]"
          placeholder={selectedSkillRefs.length === 0 ? "Search skills..." : ""}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsOpen(true)}
        />
      </div>

      {isOpen && (
        <div 
          className="absolute z-50 mt-2 w-full max-h-60 overflow-auto rounded-xl border shadow-xl fade-in slide-in-from-top-2"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        >
          {isLoading ? (
            <div className="p-4 text-center text-xs text-text-muted">Loading skills...</div>
          ) : availableSkills.length === 0 ? (
            <div className="p-4 text-center text-xs text-text-muted">No matching skills found</div>
          ) : (
            <div className="p-1">
              {availableSkills.map(skill => (
                <button
                  key={skill.id}
                  type="button"
                  className="w-full text-left p-3 rounded-lg hover:bg-slate-50 transition-colors group"
                  onClick={() => {
                    toggleSkill(skill.name);
                    setSearchTerm('');
                    setIsOpen(false);
                  }}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-sm font-bold group-hover:text-primary transition-colors">{skill.name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 uppercase">{skill.category}</span>
                  </div>
                  <div className="text-[11px] text-text-muted line-clamp-1">{skill.description}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
