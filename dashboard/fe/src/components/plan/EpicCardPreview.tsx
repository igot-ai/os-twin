'use client';

import React, { useState, useRef, useCallback } from 'react';
import { EpicNode, EpicSection, EpicDocument } from '@/lib/epic-parser';
import { Badge } from '@/components/ui/Badge';
import { MarkdownRenderer } from '@/lib/markdown-renderer';
import { usePlanContext } from './PlanWorkspace';
import { roleColorMap, getRoleColor } from '@/lib/role-utils';
import { useRoles } from '@/hooks/use-roles';

// Map well-known section headings to Material Symbols icons
const sectionIconMap: Record<string, string> = {
  'definition of done': 'check_circle',
  'tasks': 'task_alt',
  'acceptance criteria': 'verified',
  'description': 'article',
  'context': 'info',
};

// Known roles for the dropdown
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
  // Check exact match first, then partial
  if (roleIconMap[normalized]) return roleIconMap[normalized];
  if (normalized.includes('engineer')) return 'engineering';
  if (normalized.includes('qa')) return 'bug_report';
  return 'person';
}

/** Render inline `code` and 'highlight' spans inside plain text */
function renderInlineCode(text: string): React.ReactNode[] {
  // Step 1: Split by backtick code
  const codeparts = text.split(/(`[^`]+`)/g);
  const withCode: (string | React.ReactNode)[] = codeparts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={`c${i}`}
          className="px-1 py-0.5 rounded bg-primary/8 font-mono text-[11px] text-primary border border-primary/15"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });

  // Step 2: Split remaining strings by single-quote highlights
  return withCode.flatMap((part, i) => {
    if (typeof part !== 'string') return part;
    const subparts = part.split(/('[^']+?')/g);
    return subparts.map((sub, j) => {
      if (sub.startsWith("'") && sub.endsWith("'") && sub.length > 2) {
        return (
          <span
            key={`q${i}-${j}`}
            className="px-1 py-0.5 rounded bg-amber-50 text-amber-700 text-[11px] font-medium border border-amber-200/60"
          >
            {sub.slice(1, -1)}
          </span>
        );
      }
      return sub;
    });
  });
}

interface EpicCardPreviewProps {
  epic: EpicNode;
}

export function EpicCardPreview({ epic }: EpicCardPreviewProps) {
  const { updateParsedPlan } = usePlanContext();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editingDescription, setEditingDescription] = useState(false);
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [roleSearchQuery, setRoleSearchQuery] = useState('');
  const { roles: globalRolesList } = useRoles();
  
  const [titleValue, setTitleValue] = useState(epic.title);
  const descriptionSection = epic.sections.find(s => s.heading.toLowerCase() === 'description');
  const [descriptionValue, setDescriptionValue] = useState(descriptionSection?.content || '');
  const [addingItemSection, setAddingItemSection] = useState<string | null>(null);
  const [newItemText, setNewItemText] = useState('');
  const newItemInputRef = useRef<HTMLInputElement>(null);

  // Inline editing state for checklist items (AC + DoD)
  const [editingCheckItem, setEditingCheckItem] = useState<string | null>(null); // "sectionHeading:idx"
  const [editingCheckText, setEditingCheckText] = useState('');

  // Inline editing state for task items
  const [editingTask, setEditingTask] = useState<string | null>(null); // "sectionHeading:taskId"
  const [editingTaskTitle, setEditingTaskTitle] = useState('');
  const [editingTaskBody, setEditingTaskBody] = useState('');

  // Sync state with props when NOT editing
  if (!editingTitle && titleValue !== epic.title) {
    setTitleValue(epic.title);
  }
  const currentDesc = epic.sections.find(s => s.heading.toLowerCase() === 'description')?.content || '';
  if (!editingDescription && descriptionValue !== currentDesc) {
    setDescriptionValue(currentDesc);
  }

  const titleInputRef = useRef<HTMLInputElement>(null);
  const descriptionTextareaRef = useRef<HTMLTextAreaElement>(null);

  const handleToggleCheckItem = (sectionHeading: string, itemIndex: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
      if (epicToUpdate) {
        const section = epicToUpdate.sections.find(s => s.heading === sectionHeading);
        if (section && section.items) {
          const item = section.items[itemIndex];
          item.checked = !item.checked;
          item.rawLine = `${item.prefix}${item.checked ? 'x' : ' '}] ${item.text}`;
        }
      }
      return doc;
    });
  };

  const handleToggleTask = (sectionHeading: string, taskIndex: number) => {
    updateParsedPlan((doc: EpicDocument) => {
      const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
      if (epicToUpdate) {
        const section = epicToUpdate.sections.find(s => s.heading === sectionHeading);
        if (section && section.tasks) {
          const task = section.tasks[taskIndex];
          task.completed = !task.completed;
          // Reconstruct rawHeader to preserve ID and delimiter
          const statusChar = task.completed ? 'x' : ' ';
          task.rawHeader = `${task.prefix}${statusChar}] ${task.idPrefix}${task.id}${task.idSuffix}${task.delimiter}${task.title}`;
        }
      }
      return doc;
    });
  };

  // ── Edit existing checklist item ──
  const handleStartEditCheckItem = (sectionHeading: string, idx: number, text: string) => {
    setEditingCheckItem(`${sectionHeading}:${idx}`);
    setEditingCheckText(text);
  };

  const handleCommitEditCheckItem = (sectionHeading: string, idx: number) => {
    const trimmed = editingCheckText.trim();
    if (trimmed) {
      updateParsedPlan((doc: EpicDocument) => {
        const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
        if (epicToUpdate) {
          const section = epicToUpdate.sections.find(s => s.heading === sectionHeading);
          if (section?.items?.[idx]) {
            section.items[idx].text = trimmed;
            section.items[idx].rawLine = `${section.items[idx].prefix}${trimmed}`;
          }
        }
        return doc;
      });
    }
    setEditingCheckItem(null);
    setEditingCheckText('');
  };

  // ── Edit existing task item ──
  const handleStartEditTask = (sectionHeading: string, taskId: string, title: string, body: string) => {
    setEditingTask(`${sectionHeading}:${taskId}`);
    setEditingTaskTitle(title);
    setEditingTaskBody(body);
  };

  const handleCommitEditTask = (sectionHeading: string, taskId: string) => {
    const trimmedTitle = editingTaskTitle.trim();
    if (trimmedTitle) {
      updateParsedPlan((doc: EpicDocument) => {
        const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
        if (epicToUpdate) {
          const section = epicToUpdate.sections.find(s => s.heading === sectionHeading);
          if (section?.tasks) {
            const task = section.tasks.find(t => t.id === taskId);
            if (task) {
              task.title = trimmedTitle;
              task.body = editingTaskBody;
              task.bodyLines = editingTaskBody ? editingTaskBody.split('\n') : [];
              // Reconstruct rawHeader
              const checkbox = task.completed ? '[x]' : '[ ]';
              task.rawHeader = `${task.prefix.replace(/\[[ x]\]/, checkbox)}${task.idPrefix}${task.id}${task.idSuffix}${task.delimiter}${trimmedTitle}`;
            }
          }
        }
        return doc;
      });
    }
    setEditingTask(null);
    setEditingTaskTitle('');
    setEditingTaskBody('');
  };

  const handleAddItem = (sectionHeading: string, text: string) => {
    if (!text.trim()) return;
    updateParsedPlan((doc: EpicDocument) => {
      const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
      if (epicToUpdate) {
        const section = epicToUpdate.sections.find(s => s.heading === sectionHeading);
        if (section) {
          if (section.type === 'checklist') {
            if (!section.items) section.items = [];
            section.items.push({
              text: text.trim(),
              checked: false,
              rawLine: `- [ ] ${text.trim()}`,
              prefix: '- [ ] '
            });
          } else if (section.type === 'tasklist') {
            if (!section.tasks) section.tasks = [];
            // Derive the task ID prefix from existing tasks (e.g. "T-G001" from "T-G001.6")
            // Fall back to "T-" + epic ref number if no existing tasks
            let idBase = '';
            let maxNum = 0;
            section.tasks.forEach(t => {
              const match = t.id.match(/^(.+)\.(\d+)$/);
              if (match) {
                idBase = match[1];
                const num = parseInt(match[2]);
                if (num > maxNum) maxNum = num;
              }
            });
            if (!idBase) {
              // Generate from epic ref: EPIC-001 → T-G001
              const refNum = epic.ref.replace(/^EPIC-/, '');
              idBase = `T-G${refNum}`;
            }
            const nextTaskId = `${idBase}.${maxNum + 1}`;
            section.tasks.push({
              id: nextTaskId,
              title: text.trim(),
              completed: false,
              body: '',
              bodyLines: [],
              rawHeader: `- [ ] **${nextTaskId}** — ${text.trim()}`,
              prefix: '- [ ] ',
              idPrefix: '**',
              idSuffix: '**',
              delimiter: ' — '
            });
          }
        }
      }
      return doc;
    });
  };

  const handleStartAddItem = useCallback((sectionHeading: string) => {
    setAddingItemSection(sectionHeading);
    setNewItemText('');
    // Focus the input after render
    setTimeout(() => newItemInputRef.current?.focus(), 50);
  }, []);

  const handleCommitNewItem = useCallback((sectionHeading: string) => {
    if (newItemText.trim()) {
      handleAddItem(sectionHeading, newItemText);
    }
    setAddingItemSection(null);
    setNewItemText('');
  }, [newItemText]);

  const handleCancelNewItem = useCallback(() => {
    setAddingItemSection(null);
    setNewItemText('');
  }, []);

  const handleTitleSubmit = () => {
    setEditingTitle(false);
    if (titleValue !== epic.title) {
      updateParsedPlan((doc: EpicDocument) => {
        const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
        if (epicToUpdate) {
          epicToUpdate.title = titleValue;
          // Reconstruct rawHeading
          const prefix = epicToUpdate.headingLevel === 3 ? '###' : '##';
          epicToUpdate.rawHeading = `${prefix} ${epicToUpdate.ref} — ${titleValue}`;
        }
        return doc;
      });
    }
  };

  const handleDescriptionSubmit = () => {
    setEditingDescription(false);
    const descSection = epic.sections.find(s => s.heading.toLowerCase() === 'description');
    if (descSection && descriptionValue !== descSection.content) {
      updateParsedPlan((doc: EpicDocument) => {
        const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
        if (epicToUpdate) {
          const section = epicToUpdate.sections.find(s => s.heading.toLowerCase() === 'description');
          if (section) {
            section.content = descriptionValue;
          }
        }
        return doc;
      });
    }
  };

  const renderSection = (section: EpicSection) => {
    // Skip the implicit frontmatter section — already rendered in the badge bar
    if (!section.heading) return null;
    if (section.type === 'text' && section.content.trim() === '') return null;

    return (
      <div key={section.heading} className="mt-4 first:mt-0">
        {section.heading && (
          <h4 className="text-[10px] font-bold text-text-faint uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              {sectionIconMap[section.heading.toLowerCase()] || 'label'}
            </span>
            {section.heading}
            <div className="h-px flex-1 bg-border/50" />
          </h4>
        )}
        
        {section.type === 'text' && (() => {
          // Strip heading lines from content to avoid duplicate rendering
          const cleanContent = section.content.split('\n').filter(l => !l.match(/^#{1,6}\s/)).join('\n').trim();
          if (section.heading.toLowerCase() === 'description') {
            return editingDescription ? (
              <textarea
                ref={descriptionTextareaRef}
                value={descriptionValue}
                onChange={(e) => setDescriptionValue(e.target.value)}
                onBlur={handleDescriptionSubmit}
                className="w-full bg-background border border-primary px-3 py-2 rounded text-sm min-h-[100px] focus:outline-none focus:ring-2 focus:ring-primary/20 resize-y font-mono"
                autoFocus
              />
            ) : (
              <div 
                className="cursor-text hover:bg-surface-hover/50 p-2 -m-2 rounded transition-colors"
                onDoubleClick={() => setEditingDescription(true)}
                data-testid="epic-description"
              >
                <MarkdownRenderer content={cleanContent} className="text-sm text-text-main" />
              </div>
            );
          }
          return cleanContent ? (
            <MarkdownRenderer content={cleanContent} className="text-sm text-text-main" />
          ) : null;
        })()}

        {section.type === 'checklist' && section.items && (
          <div className="ml-1">
            {section.preamble && section.preamble.length > 0 && (() => {
              const filtered = section.preamble.filter(l => !l.match(/^#{1,6}\s/));
              return filtered.length > 0 ? (
                <MarkdownRenderer content={filtered.join('\n')} className="text-sm text-text-main mb-2" />
              ) : null;
            })()}
            <div className="space-y-1">
              {section.items.map((item, idx) => {
                const isAC = section.heading.toLowerCase() === 'acceptance criteria';
                const checkKey = `${section.heading}:${idx}`;
                const isEditing = editingCheckItem === checkKey;
                return (
                  <div key={idx} className="flex items-start gap-2 group/item">
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={() => handleToggleCheckItem(section.heading, idx)}
                      className={`mt-1 h-3.5 w-3.5 rounded border-border focus:ring-primary/20 cursor-pointer ${
                        isAC ? (item.checked ? 'text-success' : 'text-danger') : 'text-primary'
                      }`}
                    />
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingCheckText}
                        onChange={(e) => setEditingCheckText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') { e.preventDefault(); handleCommitEditCheckItem(section.heading, idx); }
                          if (e.key === 'Escape') { setEditingCheckItem(null); setEditingCheckText(''); }
                        }}
                        onBlur={() => handleCommitEditCheckItem(section.heading, idx)}
                        className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-0.5 rounded text-sm text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        autoFocus
                      />
                    ) : (
                      <span
                        className={`text-sm leading-relaxed transition-colors cursor-text hover:bg-surface-hover/50 px-1 -mx-1 rounded ${
                          item.checked ? (isAC ? 'text-success-text font-medium' : 'text-text-muted line-through') : (isAC ? 'text-danger-text' : 'text-text-main')
                        }`}
                        onClick={(e) => { e.stopPropagation(); handleStartEditCheckItem(section.heading, idx, item.text); }}
                        title="Click to edit"
                        data-testid="check-item"
                      >
                        {renderInlineCode(item.text)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            {addingItemSection === section.heading ? (
              <div className="flex items-center gap-2 mt-2 pl-1">
                <input
                  type="checkbox"
                  disabled
                  className="h-3.5 w-3.5 rounded border-border opacity-40"
                />
                <input
                  ref={newItemInputRef}
                  type="text"
                  value={newItemText}
                  onChange={(e) => setNewItemText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleCommitNewItem(section.heading);
                    }
                    if (e.key === 'Escape') handleCancelNewItem();
                  }}
                  onBlur={() => handleCommitNewItem(section.heading)}
                  placeholder="Type new item and press Enter…"
                  className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1 rounded text-sm text-text-main placeholder:text-text-faint/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  autoFocus
                />
                <button
                  onMouseDown={(e) => { e.preventDefault(); handleCancelNewItem(); }}
                  className="p-0.5 rounded hover:bg-red-50 transition-colors"
                  title="Cancel"
                >
                  <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500">close</span>
                </button>
              </div>
            ) : (
              <button 
                onClick={() => handleStartAddItem(section.heading)}
                className="flex items-center gap-1.5 text-[10px] font-bold text-primary hover:text-primary-dark transition-colors mt-2 uppercase tracking-wider pl-1"
              >
                <span className="material-symbols-outlined text-[14px]">add_circle</span>
                Add item
              </button>
            )}
            {section.postamble && section.postamble.length > 0 && (
              <MarkdownRenderer content={section.postamble.join('\n')} className="text-sm text-text-main mt-2" />
            )}
          </div>
        )}

        {section.type === 'tasklist' && section.tasks && (
          <div className="mt-2">
            {section.preamble && section.preamble.length > 0 && (() => {
              const filtered = section.preamble.filter(l => !l.match(/^#{1,6}\s/));
              return filtered.length > 0 ? (
                <MarkdownRenderer content={filtered.join('\n')} className="text-sm text-text-main mb-3" />
              ) : null;
            })()}
            <div className="space-y-3">
              {section.tasks.map((task, idx) => {
                const taskKey = `${section.heading}:${task.id}`;
                const isEditingThisTask = editingTask === taskKey;
                return (
                  <div key={task.id} className={`p-3 rounded-lg border transition-colors ${
                    isEditingThisTask 
                      ? 'border-primary bg-background shadow-md' 
                      : 'border-border bg-background/50 hover:border-text-faint'
                  }`} data-testid="task-item">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={task.completed}
                        onChange={() => handleToggleTask(section.heading, idx)}
                        className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary/20 cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        {isEditingThisTask ? (
                          <div className="space-y-2">
                            {/* Task title input */}
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="font-mono text-[9px] px-1 py-0 h-4 shrink-0">{task.id}</Badge>
                              <input
                                type="text"
                                value={editingTaskTitle}
                                onChange={(e) => setEditingTaskTitle(e.target.value)}
                                className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1 rounded text-sm font-bold text-text-main focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                                autoFocus
                              />
                            </div>
                            {/* Task body markdown editor */}
                            <textarea
                              value={editingTaskBody}
                              onChange={(e) => setEditingTaskBody(e.target.value)}
                              placeholder="Task details (markdown supported)…"
                              className="w-full bg-background border border-border focus:border-primary px-3 py-2 rounded text-xs text-text-main font-mono min-h-[80px] focus:outline-none focus:ring-2 focus:ring-primary/20 resize-y transition-all placeholder:text-text-faint/40"
                              rows={Math.max(3, editingTaskBody.split('\n').length + 1)}
                            />
                            {/* Action buttons */}
                            <div className="flex items-center gap-2 justify-end">
                              <button
                                onMouseDown={(e) => { e.preventDefault(); setEditingTask(null); }}
                                className="px-3 py-1 text-[10px] font-bold text-text-faint hover:text-text-main rounded-md border border-border hover:bg-surface-hover transition-all uppercase tracking-wider"
                              >
                                Cancel
                              </button>
                              <button
                                onMouseDown={(e) => { e.preventDefault(); handleCommitEditTask(section.heading, task.id); }}
                                className="px-3 py-1 text-[10px] font-bold text-white bg-primary hover:bg-primary-dark rounded-md shadow-sm transition-all uppercase tracking-wider"
                              >
                                Save
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div 
                            className="cursor-text hover:bg-surface-hover/30 p-1 -m-1 rounded transition-colors"
                            onClick={(e) => { e.stopPropagation(); handleStartEditTask(section.heading, task.id, task.title, task.body); }}
                            title="Click to edit task"
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="font-mono text-[9px] px-1 py-0 h-4">{task.id}</Badge>
                              <span className={`text-sm font-bold truncate ${task.completed ? 'text-text-muted line-through' : 'text-text-main'}`}>
                                {renderInlineCode(task.title)}
                              </span>
                            </div>
                            {task.body && (
                              <MarkdownRenderer content={task.body} className="mt-2 text-xs text-text-muted" />
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {addingItemSection === section.heading ? (
              <div className="flex items-center gap-2 mt-3 px-3">
                <input
                  type="checkbox"
                  disabled
                  className="h-4 w-4 rounded border-border opacity-40"
                />
                <input
                  ref={newItemInputRef}
                  type="text"
                  value={newItemText}
                  onChange={(e) => setNewItemText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleCommitNewItem(section.heading);
                    }
                    if (e.key === 'Escape') handleCancelNewItem();
                  }}
                  onBlur={() => handleCommitNewItem(section.heading)}
                  placeholder="Type new task title and press Enter…"
                  className="flex-1 bg-background border border-primary/40 focus:border-primary px-2 py-1.5 rounded text-sm font-bold text-text-main placeholder:text-text-faint/50 placeholder:font-normal focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  autoFocus
                />
                <button
                  onMouseDown={(e) => { e.preventDefault(); handleCancelNewItem(); }}
                  className="p-0.5 rounded hover:bg-red-50 transition-colors"
                  title="Cancel"
                >
                  <span className="material-symbols-outlined text-[14px] text-text-faint hover:text-red-500">close</span>
                </button>
              </div>
            ) : (
              <button 
                onClick={() => handleStartAddItem(section.heading)}
                className="w-full py-2 mt-3 border border-dashed border-border rounded-lg text-[10px] font-bold text-text-faint hover:text-primary hover:border-primary transition-all flex items-center justify-center gap-1.5 uppercase tracking-wider"
              >
                <span className="material-symbols-outlined text-[14px]">add_circle</span>
                Add task
              </button>
            )}
            {section.postamble && section.postamble.length > 0 && (
              <MarkdownRenderer content={section.postamble.join('\n')} className="text-sm text-text-main mt-3" />
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div 
      id={epic.ref}
      className={`mb-6 rounded-xl border bg-surface shadow-sm overflow-hidden transition-all duration-200 ${
        isCollapsed ? 'hover:border-text-faint' : 'border-border'
      }`}
      data-testid="epic-card"
    >
      {/* Header */}
      <div 
        className={`px-4 py-3 flex items-center justify-between cursor-pointer select-none bg-background/20 ${
          isCollapsed ? '' : 'border-b border-border'
        }`}
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Badge variant="primary" className="font-bold">{epic.ref}</Badge>
          
          {editingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={titleValue}
              onChange={(e) => setTitleValue(e.target.value)}
              onBlur={handleTitleSubmit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleTitleSubmit();
                if (e.key === 'Escape') {
                  setEditingTitle(false);
                  setTitleValue(epic.title);
                }
              }}
              className="bg-background border border-primary px-2 py-0.5 rounded text-sm font-bold w-full focus:outline-none focus:ring-2 focus:ring-primary/20"
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          ) : (
            <h3 
              className="text-sm font-bold text-text-main truncate hover:text-primary transition-colors"
              onDoubleClick={(e) => {
                e.stopPropagation();
                setEditingTitle(true);
              }}
              data-testid="epic-title"
            >
              {epic.title}
            </h3>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          {/* Frontmatter Badges in Header when collapsed */}
          {isCollapsed && Array.from(epic.frontmatter.entries()).slice(0, 2).map(([key, value]) => (
            <Badge key={key} variant="muted" className="hidden sm:inline-flex capitalize">{value}</Badge>
          ))}
          <span className="material-symbols-outlined text-text-faint transition-transform duration-200" style={{ transform: isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}>
            expand_more
          </span>
        </div>
      </div>

      {/* Content */}
      {!isCollapsed && (
        <div className="p-4 bg-surface">
          {/* Frontmatter Bar */}
          <div className="flex flex-wrap gap-3 mb-6 pb-4 border-b border-border/50">
            {Array.from(epic.frontmatter.entries())
              .filter(([key]) => key.toLowerCase() !== 'owner' && key.toLowerCase() !== 'roles')
              .map(([key, value]) => (
                <div key={key} className="flex flex-col gap-1">
                  <span className="text-[10px] font-bold text-text-faint uppercase tracking-tighter">{key}</span>
                  <Badge variant="secondary" className="font-medium">{value}</Badge>
                </div>
              ))}
            {/* Roles (merged from Owner / Roles fields) */}
            {(() => {
              const rolesKey = epic.frontmatter.has('Roles') ? 'Roles' : epic.frontmatter.has('roles') ? 'roles' : epic.frontmatter.has('Owner') ? 'Owner' : 'owner';
              const rolesRaw = epic.frontmatter.get(rolesKey) || '';
              const roles = rolesRaw.split(',').map((r: string) => r.trim()).filter(Boolean);

              const handleRemoveRole = (roleToRemove: string) => {
                updateParsedPlan((doc) => {
                  const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
                  if (epicToUpdate) {
                    const newRoles = roles.filter(r => r !== roleToRemove);
                    const targetKey = epicToUpdate.frontmatter.has('Roles') ? 'Roles' : epicToUpdate.frontmatter.has('Owner') ? 'Owner' : 'Roles';
                    epicToUpdate.frontmatter.set(targetKey, newRoles.join(', '));
                  }
                  return doc;
                });
              };

              const handleAddRole = (newRole: string) => {
                if (roles.includes(newRole)) return;
                updateParsedPlan((doc) => {
                  const epicToUpdate = doc.epics.find(e => e.ref === epic.ref);
                  if (epicToUpdate) {
                    const updatedRoles = [...roles, newRole];
                    const targetKey = epicToUpdate.frontmatter.has('Roles') ? 'Roles' : epicToUpdate.frontmatter.has('Owner') ? 'Owner' : 'Roles';
                    epicToUpdate.frontmatter.set(targetKey, updatedRoles.join(', '));
                  }
                  return doc;
                });
                setShowRoleDropdown(false);
              };

              const dynamicRoleNames = globalRolesList?.map(r => r.name) || [];
              const mergedAllRoles = Array.from(new Set([...KNOWN_ROLES, ...dynamicRoleNames]));
              
              const availableRoles = mergedAllRoles.filter(r => !roles.map(x => x.toLowerCase()).includes(r.toLowerCase()));

              return (
                <div className="flex flex-col gap-1 relative">
                  <span className="text-[10px] font-bold text-text-faint uppercase tracking-tighter">Roles</span>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {roles.map((role: string) => (
                      <span
                        key={role}
                        className="group/role inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border transition-all cursor-default"
                        style={{
                          backgroundColor: `${getRoleColor(role)}12`,
                          borderColor: `${getRoleColor(role)}30`,
                          color: getRoleColor(role)
                        }}
                      >
                        <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                          {getRoleIcon(role)}
                        </span>
                        {role}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRemoveRole(role); }}
                          className="opacity-0 group-hover/role:opacity-100 ml-0.5 rounded-full hover:bg-red-100 transition-all p-0 leading-none"
                          title={`Remove ${role}`}
                        >
                          <span className="material-symbols-outlined text-[12px] text-red-400 hover:text-red-600">close</span>
                        </button>
                      </span>
                    ))}
                    {/* Add role button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowRoleDropdown(!showRoleDropdown); setRoleSearchQuery(''); }}
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
                      <div className="absolute top-full left-0 mt-1 z-[101] bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[200px] flex flex-col max-h-[320px] animate-in fade-in zoom-in-95 duration-100">
                        <div className="px-2 pb-1.5 pt-1 border-b border-border/50 sticky top-0 bg-surface z-10 shrink-0">
                          <div className="relative">
                            <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-[14px] text-text-faint">search</span>
                            <input
                              type="text"
                              placeholder="Search roles..."
                              value={roleSearchQuery}
                              onChange={(e) => setRoleSearchQuery(e.target.value)}
                              className="w-full bg-background border border-border rounded px-2 py-1.5 pl-7 text-xs text-text-main focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 placeholder:text-text-faint transition-all"
                              onClick={(e) => e.stopPropagation()}
                              autoFocus
                            />
                          </div>
                        </div>
                        <div className="overflow-y-auto custom-scrollbar overflow-x-hidden py-1">
                          {filteredAvailableRoles.length === 0 ? (
                            <div className="px-3 py-3 text-xs text-text-faint italic text-center">No matching roles</div>
                          ) : (
                            filteredAvailableRoles.map(role => (
                              <button
                                key={role}
                                onClick={(e) => { e.stopPropagation(); handleAddRole(role); setRoleSearchQuery(''); }}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-text-main hover:bg-surface-alt transition-colors capitalize text-left"
                              >
                                <span
                                  className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: getRoleColor(role) }}
                                />
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
                  )})()}
                </div>
              );
            })()}
          </div>

          <div className="space-y-6">
            {epic.sections.map(section => renderSection(section))}
          </div>

          {/* Footer / Dependencies */}
          {epic.depends_on.length > 0 && (
            <div className="mt-8 pt-4 border-t border-border flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-bold text-text-faint uppercase tracking-wider">Depends on:</span>
              {epic.depends_on.map(ref => (
                <button
                  key={ref}
                  onClick={(e) => {
                    e.stopPropagation();
                    const el = document.getElementById(ref);
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }}
                  className="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-bold border border-primary/20 hover:bg-primary/20 transition-colors"
                >
                  {ref}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
