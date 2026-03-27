'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Skill } from '@/types';

export interface SkillOverrides {
  skill_refs: string[];
  disabled_skills: string[];
}

interface RoleSkillManagerProps {
  roleName: string;
  overrides: SkillOverrides;
  allSkills: Skill[];
  onToggleDisabled: (skillName: string) => void;
  onRemove: (skillName: string) => void;
  onAdd: (skillName: string) => void;
}

export default function RoleSkillManager({
  roleName,
  overrides,
  allSkills,
  onToggleDisabled,
  onRemove,
  onAdd,
}: RoleSkillManagerProps) {
  const { skill_refs: skillRefs, disabled_skills: disabledSkills } = overrides;
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsAddOpen(false);
        setSearchTerm('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const availableSkills = useCallback(() => {
    return allSkills.filter((s) => {
      if (skillRefs.includes(s.name)) return false;
      if (s.applicable_roles.length > 0 && !s.applicable_roles.includes(roleName)) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return s.name.toLowerCase().includes(term) || s.description.toLowerCase().includes(term);
      }
      return true;
    });
  }, [allSkills, skillRefs, roleName, searchTerm]);

  const handleAdd = (skillName: string) => {
    onAdd(skillName);
    setIsAddOpen(false);
    setSearchTerm('');
  };

  const filtered = availableSkills();

  return (
    <div className="mt-4">
      <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-2">
        Skills
      </label>

      <div className="flex flex-wrap gap-1.5">
        {skillRefs.length === 0 && (
          <span className="text-[10px] text-text-faint italic">No skills assigned</span>
        )}
        {skillRefs.map((skillName) => {
          const isDisabled = disabledSkills.includes(skillName);
          return (
            <span
              key={skillName}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border transition-all ${
                isDisabled
                  ? 'bg-surface-hover border-border text-text-faint line-through opacity-60'
                  : 'bg-primary-muted border-primary/20 text-primary'
              }`}
            >
              <button
                type="button"
                onClick={() => onToggleDisabled(skillName)}
                className="flex items-center"
                title={isDisabled ? 'Enable skill' : 'Disable skill'}
              >
                <span className="material-symbols-outlined text-[13px]">
                  {isDisabled ? 'toggle_off' : 'toggle_on'}
                </span>
              </button>
              {skillName}
              <button
                type="button"
                onClick={() => onRemove(skillName)}
                className="hover:opacity-70 ml-0.5"
                title="Remove skill"
              >
                <span className="material-symbols-outlined text-[10px] leading-none">close</span>
              </button>
            </span>
          );
        })}
      </div>

      <div className="relative mt-2" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => {
            setIsAddOpen(!isAddOpen);
            setSearchTerm('');
          }}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-text-muted border border-dashed border-border hover:border-primary hover:text-primary transition-colors"
        >
          <span className="material-symbols-outlined text-[14px]">add</span>
          Add skill
        </button>

        {isAddOpen && (
          <div className="absolute z-50 mt-1 w-64 max-h-48 overflow-auto rounded-lg border border-border bg-surface shadow-xl">
            <div className="p-2 border-b border-border">
              <input
                type="text"
                className="w-full bg-background border border-border rounded px-2 py-1 text-xs text-text-main placeholder:text-text-faint focus:outline-none focus:ring-1 focus:ring-primary/30"
                placeholder="Search skills..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                autoFocus
              />
            </div>
            {filtered.length === 0 ? (
              <div className="p-3 text-center text-[10px] text-text-faint">
                No matching skills available
              </div>
            ) : (
              <div className="p-1">
                {filtered.map((skill) => (
                  <button
                    key={skill.name}
                    type="button"
                    className="w-full text-left px-3 py-2 rounded hover:bg-surface-hover transition-colors group"
                    onClick={() => handleAdd(skill.name)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-text-main group-hover:text-primary transition-colors">
                        {skill.name}
                      </span>
                      {skill.category && (
                        <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-surface-hover text-text-faint uppercase">
                          {skill.category}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-text-faint line-clamp-1 mt-0.5">
                      {skill.description}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
