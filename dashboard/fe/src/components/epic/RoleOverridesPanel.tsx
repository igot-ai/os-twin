'use client';

import React, { useState } from 'react';
import { Epic, Role, Skill } from '@/types';
import { useEpicRoles } from '@/hooks/use-epics';
import { useSkills } from '@/hooks/use-skills';
import Modal from '@/components/ui/Modal';
import Button from '@/components/ui/Button';

interface RoleOverridesPanelProps {
  epic: Epic;
}

export default function RoleOverridesPanel({ epic }: RoleOverridesPanelProps) {
  const { roles, roomOverrides, updateRoleConfig, isLoading } = useEpicRoles(epic.plan_id, epic.epic_ref);
  const { skills: allSkills } = useSkills();
  const [editingRole, setEditingRole] = useState<any | null>(null);
  const [previewRole, setPreviewRole] = useState<any | null>(null);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  const handleEditRole = (role: any) => {
    const overrides = roomOverrides[role.name] || {};
    setEditingRole({
      ...role,
      model: overrides.default_model || role.default_model,
      temperature: overrides.temperature !== undefined ? overrides.temperature : (role.temperature || 0.7),
      skill_refs: overrides.skill_refs || role.skill_refs || []
    });
  };

  const handleSaveRole = async () => {
    if (!editingRole) return;
    
    await updateRoleConfig(editingRole.name, {
      default_model: editingRole.model,
      temperature: editingRole.temperature,
      skill_refs: editingRole.skill_refs
    });
    setEditingRole(null);
  };

  const handlePreviewPrompt = async (role: any) => {
    setPreviewRole(role);
    setIsPreviewLoading(true);
    try {
      const resp = await fetch(`/api/plans/${epic.plan_id}/epics/${epic.epic_ref}/roles/${role.name}/preview`);
      const data = await resp.json();
      setPreviewContent(data.prompt || 'Failed to generate preview.');
    } catch (err) {
      setPreviewContent('Error fetching preview.');
    } finally {
      setIsPreviewLoading(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-text-faint">Loading role configurations...</div>;
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Panel Header */}
      <div className="p-4 border-b border-border bg-surface-hover/30 shrink-0 flex items-center justify-between">
        <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm" aria-hidden="true">settings_input_component</span> Role Overrides
        </h2>
      </div>

      {/* Role Overrides Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
        {roles.map((role) => {
          const isOverridden = !!roomOverrides[role.name];
          return (
            <div 
              key={role.name} 
              className={`p-3 rounded border ${
                isOverridden 
                  ? 'border-primary/30 bg-primary-muted/20' 
                  : 'border-border bg-surface'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-text-main">{role.name}</span>
                <div className="flex items-center gap-2">
                   <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                    isOverridden 
                      ? 'bg-primary text-white' 
                      : 'bg-surface-hover text-text-muted'
                  }`}>
                    {isOverridden ? 'Overridden' : 'Inherited'}
                  </span>
                  <button 
                    onClick={() => handleEditRole(role)}
                    className="p-1 hover:bg-surface-hover rounded text-text-faint hover:text-primary transition-colors"
                    title="Edit Overrides"
                  >
                    <span className="material-symbols-outlined text-sm">edit</span>
                  </button>
                   <button 
                    onClick={() => handlePreviewPrompt(role)}
                    className="p-1 hover:bg-surface-hover rounded text-text-faint hover:text-secondary transition-colors"
                    title="Preview System Prompt"
                  >
                    <span className="material-symbols-outlined text-sm">visibility</span>
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-faint uppercase font-bold tracking-tighter">Model</span>
                  <div className="text-[11px] font-medium text-text-muted">
                    {role.default_model}
                  </div>
                </div>
                <div className="flex flex-col">
                   <span className="text-[9px] text-text-faint uppercase font-bold tracking-tighter">Temperature</span>
                   <div className="text-[11px] font-medium text-text-muted">
                    {role.temperature !== undefined ? role.temperature : 0.7}
                  </div>
                </div>
                <div className="flex flex-col">
                  <span className="text-[9px] text-text-faint uppercase font-bold tracking-tighter">Skills</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(role.skill_refs || []).length > 0 ? (
                      (role.skill_refs || []).map((skill: string) => (
                        <span key={skill} className="px-1.5 py-0.5 bg-surface border border-primary/20 text-primary text-[9px] rounded">
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span className="text-[9px] text-text-faint italic">No extra skills attached</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Edit Override Modal */}
      {editingRole && (
        <Modal 
          isOpen={!!editingRole} 
          onClose={() => setEditingRole(null)}
          title={`Override Configuration: ${editingRole.name}`}
        >
          <div className="space-y-4 p-4">
            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase mb-1">Model</label>
              <input 
                type="text" 
                className="w-full bg-surface border border-border rounded px-3 py-2 text-xs focus:ring-1 focus:ring-primary outline-none"
                value={editingRole.model}
                onChange={(e) => setEditingRole({ ...editingRole, model: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase mb-1">Temperature ({editingRole.temperature})</label>
              <input 
                type="range" 
                min="0" 
                max="2" 
                step="0.1"
                className="w-full accent-primary"
                value={editingRole.temperature}
                onChange={(e) => setEditingRole({ ...editingRole, temperature: parseFloat(e.target.value) })}
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold text-text-muted uppercase mb-1">Attached Skills</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded p-2 space-y-1 bg-surface-hover/10">
                {allSkills?.map(skill => {
                  const isChecked = editingRole.skill_refs.includes(skill.name);
                  return (
                    <label key={skill.name} className="flex items-center gap-2 px-2 py-1 hover:bg-surface-hover rounded cursor-pointer group">
                      <input 
                        type="checkbox" 
                        className="accent-primary"
                        checked={isChecked}
                        onChange={(e) => {
                          const refs = e.target.checked 
                            ? [...editingRole.skill_refs, skill.name]
                            : editingRole.skill_refs.filter((r: string) => r !== skill.name);
                          setEditingRole({ ...editingRole, skill_refs: refs });
                        }}
                      />
                      <div className="flex flex-col overflow-hidden">
                        <span className="text-xs font-medium text-text-main group-hover:text-primary transition-colors truncate">{skill.name}</span>
                        <span className="text-[10px] text-text-faint truncate">{skill.description}</span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="ghost" onClick={() => setEditingRole(null)}>Cancel</Button>
              <Button variant="primary" onClick={handleSaveRole}>Save Overrides</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Preview Modal */}
      {previewRole && (
        <Modal
          isOpen={!!previewRole}
          onClose={() => setPreviewRole(null)}
          title={`System Prompt Preview: ${previewRole.name}`}
          size="lg"
        >
          <div className="p-4">
            {isPreviewLoading ? (
               <div className="h-60 flex items-center justify-center">
                 <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
               </div>
            ) : (
              <div className="bg-background-dark/5 rounded border border-border p-4 h-96 overflow-y-auto custom-scrollbar">
                <pre className="text-xs text-text-main whitespace-pre-wrap font-mono leading-relaxed">
                  {previewContent}
                </pre>
              </div>
            )}
            <div className="flex justify-end pt-4">
              <Button variant="primary" onClick={() => setPreviewRole(null)}>Close</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

