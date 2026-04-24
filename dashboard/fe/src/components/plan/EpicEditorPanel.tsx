'use client';

import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { EpicNode, EpicSection, EpicDocument, CheckItem, TaskNode } from '@/lib/epic-parser';
import { Badge } from '@/components/ui/Badge';
import { MarkdownRenderer } from '@/lib/markdown-renderer';
import { usePlanContext } from './PlanWorkspace';
import { roleColorMap, getRoleColor } from '@/lib/role-utils';
import { useRoles } from '@/hooks/use-roles';
import { DraggableChecklistItem } from './DraggableChecklistItem';
import { DraggableTaskCard } from './DraggableTaskCard';

// ── Tab definitions ────────────────────────────────────────────────────────────

type TabId = 'overview' | 'dod' | 'ac' | 'tasks' | 'deps';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: 'article' },
  { id: 'dod', label: 'DoD', icon: 'check_circle' },
  { id: 'ac', label: 'AC', icon: 'verified' },
  { id: 'tasks', label: 'Tasks', icon: 'task_alt' },
  { id: 'deps', label: 'Deps', icon: 'account_tree' },
];

// ── Role helpers ───────────────────────────────────────────────────────────────

const KNOWN_ROLES = Object.keys(roleColorMap);

const roleIconMap: Record<string, string> = {
  engineer: 'engineering',
  qa: 'bug_report',
  architect: 'architecture',
  manager: 'supervisor_account',
  designer: 'palette',
  copywriter: 'edit_note',
  auditor: 'verified_user',
  'data-analyst': 'analytics',
  system: 'settings',
};

function getRoleIcon(role: string): string {
  const normalized = role.toLowerCase();
  if (roleIconMap[normalized]) return roleIconMap[normalized];
  if (normalized.includes('engineer')) return 'engineering';
  if (normalized.includes('qa')) return 'bug_report';
  return 'person';
}

/** Render inline `code` and 'highlight' spans inside plain text */
function renderInlineCode(text: string): React.ReactNode[] {
  const codeparts = text.split(/(`[^`]+`)/g);
  const withCode: (string | React.ReactNode)[] = codeparts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={`c${i}`} className="px-1 py-0.5 rounded bg-primary/8 font-mono text-[11px] text-primary border border-primary/15">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });

  return withCode.flatMap((part, i) => {
    if (typeof part !== 'string') return part;
    const subparts = part.split(/('[^']+?')/g);
    return subparts.map((sub, j) => {
      if (sub.startsWith("'") && sub.endsWith("'") && sub.length > 2) {
        return (
          <span key={`q${i}-${j}`} className="px-1 py-0.5 rounded bg-amber-50 text-amber-700 text-[11px] font-medium border border-amber-200/60">
            {sub.slice(1, -1)}
          </span>
        );
      }
      return sub;
    });
  });
}

// ── Props ──────────────────────────────────────────────────────────────────────

export interface EpicEditorPanelProps {
  epic: EpicNode | null;
  isOpen: boolean;
  onClose: () => void;
  initialTab?: TabId;
}

// ── Component ──────────────────────────────────────────────────────────────────

export function EpicEditorPanel({ epic, isOpen, onClose, initialTab }: EpicEditorPanelProps) {
  const { updateParsedPlan, parsedPlan, savePlan } = usePlanContext();
  const [activeTab, setActiveTab] = useState<TabId>(initialTab || 'overview');
  const [isSaving, setIsSaving] = useState(false);

  // ── Reset tab when epic changes ──
  useEffect(() => {
    if (epic) {
      setActiveTab(initialTab || 'overview');
    }
  }, [epic?.ref, initialTab]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Escape key ──
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // ── Cmd+S save ──
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's' && isOpen) {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await savePlan();
    } catch (err) {
      // Toast handled by PlanWorkspace
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteEpic = () => {
    if (!epic) return;
    if (window.confirm(`Are you sure you want to delete ${epic.ref}? This action cannot be undone.`)) {
      updateParsedPlan((doc) => {
        // Mutate doc directly — updateParsedPlan ignores the return value
        doc.epics = doc.epics.filter(e => e.ref !== epic.ref);
        for (const e of doc.epics) {
          e.depends_on = e.depends_on.filter(ref => ref !== epic.ref);
        }
      });
      onClose();
    }
  };

  if (!epic) return null;

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-[2px] z-[100] transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-[580px] bg-surface shadow-2xl z-[101] transform transition-transform duration-300 ease-in-out border-l border-border flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="px-5 py-3 border-b border-border flex items-center justify-between bg-surface-alt/10 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="text-[10px] font-bold text-primary uppercase tracking-wider bg-primary/10 px-2 py-0.5 rounded border border-primary/20 shrink-0">
              {epic.ref}
            </span>
            <HeaderTitle epic={epic} />
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-surface-hover rounded-md text-text-faint transition-colors shrink-0"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex items-center border-b border-border bg-surface-alt/5 shrink-0">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wider transition-all border-b-2 ${
                activeTab === tab.id
                  ? 'text-primary border-primary bg-primary/5'
                  : 'text-text-faint border-transparent hover:text-text-main hover:bg-surface-hover'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === 'overview' && <OverviewTab epic={epic} />}
          {activeTab === 'dod' && <ChecklistTab epic={epic} sectionHeading="Definition of Done" />}
          {activeTab === 'ac' && <ChecklistTab epic={epic} sectionHeading="Acceptance Criteria" />}
          {activeTab === 'tasks' && <TasksTab epic={epic} />}
          {activeTab === 'deps' && <DepsTab epic={epic} />}
        </div>

        {/* Footer actions */}
        <div className="px-5 py-3 border-t border-border flex items-center justify-between bg-surface-alt/5 shrink-0">
          <button
            onClick={handleDeleteEpic}
            className="flex items-center gap-1.5 py-1.5 px-3 rounded-md border border-red-200 text-red-600 bg-red-50 hover:bg-red-100 transition-colors text-[11px] font-bold uppercase tracking-wider"
          >
            <span className="material-symbols-outlined text-[16px]">delete</span>
            Delete EPIC
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-1.5 py-1.5 px-4 rounded-md bg-primary text-white hover:opacity-90 transition-all text-[11px] font-bold uppercase tracking-wider disabled:opacity-50 shadow-sm"
          >
            <span className="material-symbols-outlined text-[16px]">{isSaving ? 'sync' : 'save'}</span>
            Save ⌘S
          </button>
        </div>
      </div>
    </>
  );
}

// ── Header Title (inline editable) ─────────────────────────────────────────────

function HeaderTitle({ epic }: { epic: EpicNode }) {
  const { updateParsedPlan } = usePlanContext();
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(epic.title);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync with prop when not editing
  useEffect(() => {
    if (!isEditing) setValue(epic.title);
  }, [epic.title, isEditing]);

  const commit = () => {
    setIsEditing(false);
    const trimmed = value.trim();
    if (trimmed && trimmed !== epic.title) {
      updateParsedPlan((doc: EpicDocument) => {
        const e = doc.epics.find(e => e.ref === epic.ref);
        if (e) {
          e.title = trimmed;
          const prefix = e.headingLevel === 3 ? '###' : '##';
          e.rawHeading = `${prefix} ${e.ref} — ${trimmed}`;
        }
        return doc;
      });
    }
  };

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') { setIsEditing(false); setValue(epic.title); }
        }}
        className="text-sm font-bold text-text-main bg-background border border-primary px-2 py-0.5 rounded w-full min-w-0 focus:outline-none focus:ring-2 focus:ring-primary/20"
        autoFocus
      />
    );
  }

  return (
    <h2
      className="text-sm font-bold text-text-main truncate max-w-[320px] cursor-text hover:text-primary transition-colors"
      onDoubleClick={() => setIsEditing(true)}
      title="Double-click to edit"
    >
      {epic.title}
    </h2>
  );
}

// ── Overview Tab ───────────────────────────────────────────────────────────────

function OverviewTab({ epic }: { epic: EpicNode }) {
  const { updateParsedPlan } = usePlanContext();
  const { roles: globalRolesList } = useRoles();
  const [editingDescription, setEditingDescription] = useState(false);
  const [descriptionValue, setDescriptionValue] = useState(
    epic.sections.find(s => s.heading.toLowerCase() === 'description')?.content || ''
  );
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [roleSearchQuery, setRoleSearchQuery] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync description
  useEffect(() => {
    if (!editingDescription) {
      const desc = epic.sections.find(s => s.heading.toLowerCase() === 'description')?.content || '';
      setDescriptionValue(desc);
    }
  }, [epic, editingDescription]);

  const commitDescription = () => {
    setEditingDescription(false);
    const descSection = epic.sections.find(s => s.heading.toLowerCase() === 'description');
    const currentDesc = descSection?.content || '';
    if (descriptionValue !== currentDesc) {
      updateParsedPlan((doc: EpicDocument) => {
        const e = doc.epics.find(e => e.ref === epic.ref);
        if (e) {
          const section = e.sections.find(s => s.heading.toLowerCase() === 'description');
          if (section) {
            section.content = descriptionValue;
          }
        }
        return doc;
      });
    }
  };

  // ── Role management ──
  const rolesKey = epic.frontmatter.has('Roles') ? 'Roles' : epic.frontmatter.has('roles') ? 'roles' : epic.frontmatter.has('Owner') ? 'Owner' : 'owner';
  const rolesRaw = epic.frontmatter.get(rolesKey) || '';
  const roles = rolesRaw.split(',').map((r: string) => r.trim()).filter(Boolean);

  const handleRemoveRole = (roleToRemove: string) => {
    updateParsedPlan((doc) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const currentRoles = (e.frontmatter.get('Roles') || e.frontmatter.get('Owner') || '').split(',').map((r: string) => r.trim()).filter(Boolean);
        const newRoles = currentRoles.filter(r => r !== roleToRemove);
        const targetKey = e.frontmatter.has('Roles') ? 'Roles' : e.frontmatter.has('Owner') ? 'Owner' : 'Roles';
        e.frontmatter.set(targetKey, newRoles.join(', '));
      }
      return doc;
    });
  };

  const handleAddRole = (newRole: string) => {
    if (roles.includes(newRole)) return;
    updateParsedPlan((doc) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const updatedRoles = [...roles, newRole];
        const targetKey = e.frontmatter.has('Roles') ? 'Roles' : e.frontmatter.has('Owner') ? 'Owner' : 'Roles';
        e.frontmatter.set(targetKey, updatedRoles.join(', '));
      }
      return doc;
    });
    setShowRoleDropdown(false);
  };

  const dynamicRoleNames = globalRolesList?.map(r => r.name) || [];
  const mergedAllRoles = useMemo(() =>
    Array.from(new Set([...KNOWN_ROLES, ...dynamicRoleNames])),
    [globalRolesList]
  );
  const availableRoles = mergedAllRoles.filter(r => !roles.map(x => x.toLowerCase()).includes(r.toLowerCase()));

  // ── Frontmatter editing ──
  const [editingFrontmatter, setEditingFrontmatter] = useState<string | null>(null);
  const [frontmatterValue, setFrontmatterValue] = useState('');

  const startEditFrontmatter = (key: string, value: string) => {
    setEditingFrontmatter(key);
    setFrontmatterValue(value);
  };

  const commitFrontmatter = (key: string) => {
    setEditingFrontmatter(null);
    const trimmed = frontmatterValue.trim();
    if (trimmed) {
      updateParsedPlan((doc: EpicDocument) => {
        const e = doc.epics.find(e => e.ref === epic.ref);
        if (e) {
          e.frontmatter.set(key, trimmed);
        }
        return doc;
      });
    }
  };

  const deleteFrontmatter = (key: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        e.frontmatter.delete(key);
      }
      return doc;
    });
  };

  const [newFmKey, setNewFmKey] = useState('');
  const [addingFm, setAddingFm] = useState(false);

  const addFrontmatter = () => {
    const key = newFmKey.trim();
    if (key && !epic.frontmatter.has(key)) {
      updateParsedPlan((doc: EpicDocument) => {
        const e = doc.epics.find(e => e.ref === epic.ref);
        if (e) {
          e.frontmatter.set(key, 'Value');
        }
        return doc;
      });
    }
    setNewFmKey('');
    setAddingFm(false);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1.5">Title</label>
        <HeaderTitle epic={epic} />
      </div>

      {/* Roles */}
      <div>
        <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-2">Roles</label>
        <div className="flex items-center gap-1.5 flex-wrap">
          {roles.map((role: string) => (
            <span
              key={role}
              className="group/role inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border transition-all cursor-default"
              style={{
                backgroundColor: `${getRoleColor(role)}12`,
                borderColor: `${getRoleColor(role)}30`,
                color: getRoleColor(role),
              }}
            >
              <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                {getRoleIcon(role)}
              </span>
              {role}
              <button
                onClick={() => handleRemoveRole(role)}
                className="opacity-0 group-hover/role:opacity-100 ml-0.5 rounded-full hover:bg-red-100 transition-all p-0 leading-none"
                title={`Remove ${role}`}
              >
                <span className="material-symbols-outlined text-[12px] text-red-400 hover:text-red-600">close</span>
              </button>
            </span>
          ))}
          <button
            onClick={() => { setShowRoleDropdown(!showRoleDropdown); setRoleSearchQuery(''); }}
            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold text-text-faint border border-dashed border-border hover:border-primary hover:text-primary hover:bg-primary/5 transition-all"
            title="Add role"
          >
            <span className="material-symbols-outlined text-[13px]">add</span>
          </button>
        </div>
        {/* Role dropdown */}
        {showRoleDropdown && (() => {
          const filteredAvailableRoles = availableRoles.filter(r => r.toLowerCase().includes(roleSearchQuery.toLowerCase()));
          return (
            <>
              <div className="fixed inset-0 z-[100]" onClick={() => { setShowRoleDropdown(false); setRoleSearchQuery(''); }} />
              <div className="relative z-[101] mt-2 bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[220px] max-h-[300px] flex flex-col">
                <div className="px-2 pb-1.5 pt-1 border-b border-border/50 sticky top-0 bg-surface z-10 shrink-0">
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-[14px] text-text-faint">search</span>
                    <input
                      type="text"
                      placeholder="Search roles..."
                      value={roleSearchQuery}
                      onChange={(e) => setRoleSearchQuery(e.target.value)}
                      className="w-full bg-background border border-border rounded px-2 py-1.5 pl-7 text-xs text-text-main focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20"
                      autoFocus
                    />
                  </div>
                </div>
                <div className="overflow-y-auto py-1">
                  {filteredAvailableRoles.length === 0 ? (
                    <div className="px-3 py-3 text-xs text-text-faint italic text-center">No matching roles</div>
                  ) : (
                    filteredAvailableRoles.map(role => (
                      <button
                        key={role}
                        onClick={() => handleAddRole(role)}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-main hover:bg-surface-alt transition-colors capitalize text-left"
                      >
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: getRoleColor(role) }} />
                        <span className="material-symbols-outlined text-[14px]" style={{ color: getRoleColor(role) }}>
                          {getRoleIcon(role)}
                        </span>
                        {role}
                      </button>
                    ))
                  )}
                </div>
              </div>
            </>
          );
        })()}
      </div>

      {/* Description */}
      <div>
        <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-1.5">Description</label>
        {editingDescription ? (
          <textarea
            ref={textareaRef}
            value={descriptionValue}
            onChange={(e) => setDescriptionValue(e.target.value)}
            onBlur={commitDescription}
            className="w-full bg-background border border-primary px-3 py-2 rounded text-sm min-h-[120px] focus:outline-none focus:ring-2 focus:ring-primary/20 resize-y font-mono"
            autoFocus
          />
        ) : (
          <div
            className="cursor-text hover:bg-surface-hover/50 p-3 -m-1 rounded-lg border border-transparent hover:border-border transition-all"
            onDoubleClick={() => setEditingDescription(true)}
          >
            {descriptionValue ? (
              <MarkdownRenderer content={descriptionValue} className="text-sm text-text-main" />
            ) : (
              <span className="text-sm text-text-faint italic">Double-click to add description...</span>
            )}
          </div>
        )}
      </div>

      {/* Frontmatter fields */}
      <div>
        <label className="text-[10px] font-bold text-text-faint uppercase tracking-wider block mb-2">Metadata</label>
        <div className="space-y-2">
          {Array.from(epic.frontmatter.entries())
            .filter(([key]) => !/^Roles?$/i.test(key) && key.toLowerCase() !== 'owner')
            .map(([key, value]) => (
              <div key={key} className="flex items-center gap-2 group/fm">
                <span className="text-[10px] font-bold text-text-faint uppercase tracking-tighter min-w-[80px]">{key}</span>
                {editingFrontmatter === key ? (
                  <input
                    type="text"
                    value={frontmatterValue}
                    onChange={(e) => setFrontmatterValue(e.target.value)}
                    onBlur={() => commitFrontmatter(key)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitFrontmatter(key);
                      if (e.key === 'Escape') setEditingFrontmatter(null);
                    }}
                    className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1 rounded text-xs text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20"
                    autoFocus
                  />
                ) : (
                  <span
                    className="flex-1 text-xs text-text-main cursor-text hover:bg-surface-hover/50 px-1 -mx-1 rounded transition-colors"
                    onClick={() => startEditFrontmatter(key, value)}
                  >
                    {value}
                  </span>
                )}
                <button
                  onClick={() => deleteFrontmatter(key)}
                  className="opacity-0 group-hover/fm:opacity-100 p-0.5 rounded hover:bg-red-50 transition-all"
                  title={`Remove ${key}`}
                >
                  <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500">close</span>
                </button>
              </div>
            ))}
          {addingFm ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newFmKey}
                onChange={(e) => setNewFmKey(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') addFrontmatter();
                  if (e.key === 'Escape') { setAddingFm(false); setNewFmKey(''); }
                }}
                placeholder="Key name..."
                className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1 rounded text-xs text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20"
                autoFocus
              />
              <button onClick={addFrontmatter} className="p-1 rounded hover:bg-surface-hover transition-colors">
                <span className="material-symbols-outlined text-[16px] text-primary">check</span>
              </button>
              <button onClick={() => { setAddingFm(false); setNewFmKey(''); }} className="p-1 rounded hover:bg-surface-hover transition-colors">
                <span className="material-symbols-outlined text-[16px] text-text-faint">close</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAddingFm(true)}
              className="flex items-center gap-1.5 text-[10px] font-bold text-primary hover:text-primary-dark transition-colors uppercase tracking-wider"
            >
              <span className="material-symbols-outlined text-[14px]">add_circle</span>
              Add field
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Checklist Tab (DoD + AC) ───────────────────────────────────────────────────

function ChecklistTab({ epic, sectionHeading }: { epic: EpicNode; sectionHeading: string }) {
  const { updateParsedPlan } = usePlanContext();
  const [addingItem, setAddingItem] = useState(false);
  const [newItemText, setNewItemText] = useState('');
  const newItemRef = useRef<HTMLInputElement>(null);

  // ── Drag-and-drop state ──
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const section = epic.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());

  // Ensure section exists
  const items: CheckItem[] = section?.items || [];

  // ── Item operations ──

  const handleToggle = (idx: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (s?.items?.[idx]) {
          s.items[idx].checked = !s.items[idx].checked;
          s.items[idx].rawLine = `- [${s.items[idx].checked ? 'x' : ' '}] ${s.items[idx].text}`;
        }
      }
      return doc;
    });
  };

  const handleEdit = (idx: number, newText: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (s?.items?.[idx]) {
          s.items[idx].text = newText;
          s.items[idx].rawLine = `- [${s.items[idx].checked ? 'x' : ' '}] ${newText}`;
        }
      }
      return doc;
    });
  };

  const handleDeleteItem = (idx: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (s?.items) {
          s.items.splice(idx, 1);
        }
      }
      return doc;
    });
  };

  const handleAddItem = () => {
    if (!newItemText.trim()) return;
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        let s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (!s) {
          s = {
            heading: sectionHeading,
            headingLevel: 3,
            sectionKey: sectionHeading.toLowerCase().replace(/\s+/g, '_'),
            type: 'checklist',
            content: '',
            items: [],
            rawLines: [],
            preamble: [],
            postamble: [],
          };
          e.sections.push(s);
        }
        if (!s.items) s.items = [];
        s.items.push({
          text: newItemText.trim(),
          checked: false,
          rawLine: `- [ ] ${newItemText.trim()}`,
          prefix: '- [ ] ',
        });
      }
      return doc;
    });
    setNewItemText('');
    setAddingItem(false);
  };

  // ── Drag-and-drop reorder ──

  const handleDragStart = (idx: number) => {
    setDragIndex(idx);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragOver = (idx: number) => {
    setDragOverIndex(idx);
  };

  const handleDrop = (targetIdx: number) => {
    if (dragIndex === null || dragIndex === targetIdx) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }

    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (s?.items) {
          const item = s.items.splice(dragIndex, 1)[0];
          s.items.splice(targetIdx, 0, item);
        }
      }
      return doc;
    });

    setDragIndex(null);
    setDragOverIndex(null);
  };

  // ── Bulk toggle ──

  const handleBulkToggle = (checked: boolean) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === sectionHeading.toLowerCase());
        if (s?.items) {
          s.items.forEach(item => {
            item.checked = checked;
            item.rawLine = `- [${checked ? 'x' : ' '}] ${item.text}`;
          });
        }
      }
      return doc;
    });
  };

  const allChecked = items.length > 0 && items.every(i => i.checked);
  const allUnchecked = items.length > 0 && items.every(i => !i.checked);
  const isAC = sectionHeading.toLowerCase() === 'acceptance criteria';

  return (
    <div>
      {/* Bulk toggle bar */}
      {items.length > 1 && (
        <div className="flex items-center gap-2 mb-3">
          <button
            onClick={() => handleBulkToggle(true)}
            disabled={allChecked}
            className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider border border-border hover:border-primary/30 hover:bg-primary/5 hover:text-primary transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[13px]">done_all</span>
            Mark all done
          </button>
          <button
            onClick={() => handleBulkToggle(false)}
            disabled={allUnchecked}
            className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider border border-border hover:border-primary/30 hover:bg-primary/5 hover:text-primary transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[13px]">remove_done</span>
            Mark all pending
          </button>
        </div>
      )}

      {items.length === 0 && !addingItem && (
        <div className="text-center py-8 text-text-faint">
          <span className="material-symbols-outlined text-[32px] mb-2 block opacity-40">
            {isAC ? 'verified' : 'check_circle'}
          </span>
          <p className="text-xs">No {sectionHeading} items yet.</p>
          <button
            onClick={() => { setAddingItem(true); setTimeout(() => newItemRef.current?.focus(), 50); }}
            className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-primary hover:text-primary-dark uppercase tracking-wider"
          >
            <span className="material-symbols-outlined text-[14px]">add_circle</span>
            Add first item
          </button>
        </div>
      )}

      <div className="space-y-0.5 group">
        {items.map((item, idx) => (
          <DraggableChecklistItem
            key={`${epic.ref}-${sectionHeading}-${idx}`}
            item={item}
            index={idx}
            isDragOver={dragOverIndex === idx}
            isAC={isAC}
            onToggle={handleToggle}
            onEdit={handleEdit}
            onDelete={handleDeleteItem}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
          />
        ))}
      </div>

      {/* Add item */}
      {addingItem ? (
        <div className="flex items-center gap-2 mt-3 pl-7">
          <input
            ref={newItemRef}
            type="text"
            value={newItemText}
            onChange={(e) => setNewItemText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); handleAddItem(); }
              if (e.key === 'Escape') { setAddingItem(false); setNewItemText(''); }
            }}
            onBlur={() => { if (newItemText.trim()) handleAddItem(); else { setAddingItem(false); setNewItemText(''); } }}
            placeholder="Type new item and press Enter…"
            className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1.5 rounded text-sm text-text-main placeholder:text-text-faint/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
            autoFocus
          />
          <button
            onMouseDown={(e) => { e.preventDefault(); setAddingItem(false); setNewItemText(''); }}
            className="p-0.5 rounded hover:bg-red-50 transition-colors"
            title="Cancel"
          >
            <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500">close</span>
          </button>
        </div>
      ) : items.length > 0 && (
        <button
          onClick={() => { setAddingItem(true); setTimeout(() => newItemRef.current?.focus(), 50); }}
          className="flex items-center gap-1.5 text-[10px] font-bold text-primary hover:text-primary-dark transition-colors mt-3 uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-[14px]">add_circle</span>
          Add item
        </button>
      )}
    </div>
  );
}

// ── Tasks Tab ──────────────────────────────────────────────────────────────────

function TasksTab({ epic }: { epic: EpicNode }) {
  const { updateParsedPlan } = usePlanContext();
  const [addingTask, setAddingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const newTaskRef = useRef<HTMLInputElement>(null);

  // ── Drag-and-drop state ──
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const tasksSection = epic.sections.find(s => s.heading.toLowerCase() === 'tasks');
  const tasks: TaskNode[] = tasksSection?.tasks || [];

  // ── Task operations ──

  const handleToggleTask = (idx: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (s?.tasks?.[idx]) {
          const task = s.tasks[idx];
          task.completed = !task.completed;
          const statusChar = task.completed ? 'x' : ' ';
          task.rawHeader = `${task.prefix}${statusChar}] ${task.idPrefix}${task.id}${task.idSuffix}${task.delimiter}${task.title}`;
        }
      }
      return doc;
    });
  };

  const handleEditTaskTitle = (idx: number, newTitle: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (s?.tasks?.[idx]) {
          const task = s.tasks[idx];
          task.title = newTitle;
          const checkbox = task.completed ? '[x]' : '[ ]';
          task.rawHeader = `${task.prefix.replace(/\[[ x]\]/, checkbox)}${task.idPrefix}${task.id}${task.idSuffix}${task.delimiter}${newTitle}`;
        }
      }
      return doc;
    });
  };

  const handleEditTaskBody = (idx: number, newBody: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (s?.tasks?.[idx]) {
          const task = s.tasks[idx];
          task.body = newBody;
          task.bodyLines = newBody ? newBody.split('\n') : [];
        }
      }
      return doc;
    });
  };

  const handleDeleteTask = (idx: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (s?.tasks) {
          s.tasks.splice(idx, 1);
        }
      }
      return doc;
    });
  };

  const handleAddTask = () => {
    if (!newTaskTitle.trim()) return;
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        let s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (!s) {
          s = {
            heading: 'Tasks',
            headingLevel: 3,
            sectionKey: 'tasks',
            type: 'tasklist',
            content: '',
            tasks: [],
            rawLines: [],
            preamble: [],
            postamble: [],
          };
          e.sections.push(s);
        }
        if (!s.tasks) s.tasks = [];

        // Derive task ID
        let idBase = '';
        let maxNum = 0;
        s.tasks.forEach(t => {
          const match = t.id.match(/^(.+)\.(\d+)$/);
          if (match) {
            idBase = match[1];
            const num = parseInt(match[2]);
            if (num > maxNum) maxNum = num;
          }
        });
        if (!idBase) {
          const refNum = epic.ref.replace(/^EPIC-/, '');
          idBase = `T-G${refNum}`;
        }
        const nextTaskId = `${idBase}.${maxNum + 1}`;

        s.tasks.push({
          id: nextTaskId,
          title: newTaskTitle.trim(),
          completed: false,
          body: '',
          bodyLines: [],
          rawHeader: `- [ ] **${nextTaskId}** — ${newTaskTitle.trim()}`,
          prefix: '- [ ] ',
          idPrefix: '**',
          idSuffix: '**',
          delimiter: ' — ',
        });
      }
      return doc;
    });
    setNewTaskTitle('');
    setAddingTask(false);
  };

  // ── Drag-and-drop reorder ──

  const handleDragStart = (idx: number) => {
    setDragIndex(idx);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragOver = (idx: number) => {
    setDragOverIndex(idx);
  };

  const handleDrop = (targetIdx: number) => {
    if (dragIndex === null || dragIndex === targetIdx) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }

    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        const s = e.sections.find(s => s.heading.toLowerCase() === 'tasks');
        if (s?.tasks) {
          const task = s.tasks.splice(dragIndex, 1)[0];
          s.tasks.splice(targetIdx, 0, task);
        }
      }
      return doc;
    });

    setDragIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div>
      {tasks.length === 0 && !addingTask && (
        <div className="text-center py-8 text-text-faint">
          <span className="material-symbols-outlined text-[32px] mb-2 block opacity-40">task_alt</span>
          <p className="text-xs">No tasks yet.</p>
          <button
            onClick={() => { setAddingTask(true); setTimeout(() => newTaskRef.current?.focus(), 50); }}
            className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-primary hover:text-primary-dark uppercase tracking-wider"
          >
            <span className="material-symbols-outlined text-[14px]">add_circle</span>
            Add first task
          </button>
        </div>
      )}

      <div className="space-y-2 group">
        {tasks.map((task, idx) => (
          <DraggableTaskCard
            key={`${epic.ref}-task-${task.id}`}
            task={task}
            index={idx}
            isDragOver={dragOverIndex === idx}
            onToggle={handleToggleTask}
            onEditTitle={handleEditTaskTitle}
            onEditBody={handleEditTaskBody}
            onDelete={handleDeleteTask}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            renderInlineCode={renderInlineCode}
          />
        ))}
      </div>

      {/* Add task */}
      {addingTask ? (
        <div className="flex items-center gap-2 mt-3">
          <input
            ref={newTaskRef}
            type="text"
            value={newTaskTitle}
            onChange={(e) => setNewTaskTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); handleAddTask(); }
              if (e.key === 'Escape') { setAddingTask(false); setNewTaskTitle(''); }
            }}
            onBlur={() => { if (newTaskTitle.trim()) handleAddTask(); else { setAddingTask(false); setNewTaskTitle(''); } }}
            placeholder="Type new task title and press Enter…"
            className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1.5 rounded text-sm font-bold text-text-main placeholder:text-text-faint/50 placeholder:font-normal focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
            autoFocus
          />
          <button
            onMouseDown={(e) => { e.preventDefault(); setAddingTask(false); setNewTaskTitle(''); }}
            className="p-0.5 rounded hover:bg-red-50 transition-colors"
            title="Cancel"
          >
            <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500">close</span>
          </button>
        </div>
      ) : tasks.length > 0 && (
        <button
          onClick={() => { setAddingTask(true); setTimeout(() => newTaskRef.current?.focus(), 50); }}
          className="w-full py-2 mt-3 border border-dashed border-border rounded-lg text-[10px] font-bold text-text-faint hover:text-primary hover:border-primary transition-all flex items-center justify-center gap-1.5 uppercase tracking-wider"
        >
          <span className="material-symbols-outlined text-[14px]">add_circle</span>
          Add task
        </button>
      )}
    </div>
  );
}

// ── Dependencies Tab ───────────────────────────────────────────────────────────

function DepsTab({ epic }: { epic: EpicNode }) {
  const { updateParsedPlan, parsedPlan } = usePlanContext();
  const [showAddDropdown, setShowAddDropdown] = useState(false);

  // All available EPICs that can be added as dependencies
  const availableDeps = useMemo(() => {
    if (!parsedPlan) return [];
    return parsedPlan.epics
      .filter(e => e.ref !== epic.ref && !epic.depends_on.includes(e.ref))
      .map(e => ({ ref: e.ref, title: e.title }));
  }, [parsedPlan, epic.ref, epic.depends_on]);

  const handleRemoveDep = (depRef: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e) {
        e.depends_on = e.depends_on.filter(ref => ref !== depRef);
      }
      return doc;
    });
  };

  const handleAddDep = (depRef: string) => {
    updateParsedPlan((doc: EpicDocument) => {
      const e = doc.epics.find(e => e.ref === epic.ref);
      if (e && !e.depends_on.includes(depRef)) {
        e.depends_on = [...e.depends_on, depRef];
      }
      return doc;
    });
    setShowAddDropdown(false);
  };

  return (
    <div>
      {epic.depends_on.length === 0 && !showAddDropdown && (
        <div className="text-center py-8 text-text-faint">
          <span className="material-symbols-outlined text-[32px] mb-2 block opacity-40">account_tree</span>
          <p className="text-xs">No dependencies.</p>
          {availableDeps.length > 0 && (
            <button
              onClick={() => setShowAddDropdown(true)}
              className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold text-primary hover:text-primary-dark uppercase tracking-wider"
            >
              <span className="material-symbols-outlined text-[14px]">add_circle</span>
              Add dependency
            </button>
          )}
        </div>
      )}

      {/* Current dependencies */}
      {epic.depends_on.length > 0 && (
        <div className="space-y-2 mb-4">
          {epic.depends_on.map(depRef => {
            const depEpic = parsedPlan?.epics.find(e => e.ref === depRef);
            return (
              <div key={depRef} className="flex items-center gap-3 p-2.5 rounded-lg border border-border bg-background/50 group/dep hover:border-text-faint transition-colors">
                <span className="text-[10px] font-bold text-primary uppercase tracking-wider bg-primary/10 px-2 py-0.5 rounded border border-primary/20 shrink-0">
                  {depRef}
                </span>
                <span className="text-sm text-text-main truncate flex-1">
                  {depEpic?.title || depRef}
                </span>
                <button
                  onClick={() => handleRemoveDep(depRef)}
                  className="opacity-0 group-hover/dep:opacity-100 p-1 rounded hover:bg-red-50 transition-all shrink-0"
                  title={`Remove ${depRef} dependency`}
                >
                  <span className="material-symbols-outlined text-[16px] text-text-faint hover:text-red-500">close</span>
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Add dependency dropdown */}
      {showAddDropdown && (
        <>
          <div className="fixed inset-0 z-[100]" onClick={() => setShowAddDropdown(false)} />
          <div className="relative z-[101] bg-surface border border-border rounded-lg shadow-xl py-1 max-h-[280px] overflow-y-auto">
            {availableDeps.length === 0 ? (
              <div className="px-4 py-4 text-xs text-text-faint italic text-center">
                No more EPICs available to add as dependencies
              </div>
            ) : (
              availableDeps.map(dep => (
                <button
                  key={dep.ref}
                  onClick={() => handleAddDep(dep.ref)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-main hover:bg-surface-alt transition-colors text-left"
                >
                  <span className="text-[9px] font-bold text-primary uppercase tracking-wider bg-primary/10 px-1.5 py-0.5 rounded border border-primary/20">
                    {dep.ref}
                  </span>
                  <span className="truncate">{dep.title}</span>
                  <span className="material-symbols-outlined text-[14px] text-primary ml-auto">add</span>
                </button>
              ))
            )}
          </div>
        </>
      )}

      {/* Add button (when deps exist) */}
      {epic.depends_on.length > 0 && !showAddDropdown && availableDeps.length > 0 && (
        <button
          onClick={() => setShowAddDropdown(true)}
          className="flex items-center gap-1.5 text-[10px] font-bold text-primary hover:text-primary-dark transition-colors uppercase tracking-wider mt-2"
        >
          <span className="material-symbols-outlined text-[14px]">add_circle</span>
          Add dependency
        </button>
      )}
    </div>
  );
}
