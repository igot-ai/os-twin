import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Tooltip } from '@/components/ui/Tooltip';

interface Template {
  id: string;
  name: string;
  description: string;
  promptTemplate: string;
}

interface Category {
  id: string;
  name: string;
  icon: string;
  templates: Template[];
}

interface TemplatePickerProps {
  categories: Category[];
  onSelectTemplate: (prompt: string) => void;
}

export const TemplatePicker: React.FC<TemplatePickerProps> = ({ categories, onSelectTemplate }) => {
  const [activeTabId, setActiveTabId] = useState(categories[0]?.id ?? '');
  const [focusedTabIndex, setFocusedTabIndex] = useState(0);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  // Tracks whether the next focus-move should come from a keyboard event,
  // so we don't steal focus on the initial mount or on mouse clicks.
  const shouldFocusTabRef = useRef(false);

  const activeCategory = categories.find(c => c.id === activeTabId);

  useEffect(() => {
    if (!shouldFocusTabRef.current) return;
    shouldFocusTabRef.current = false;
    const el = tabRefs.current[focusedTabIndex];
    if (el) el.focus();
  }, [focusedTabIndex]);

  const moveToTab = useCallback((nextIndex: number) => {
    if (categories.length === 0) return;
    shouldFocusTabRef.current = true;
    setFocusedTabIndex(nextIndex);
    setActiveTabId(categories[nextIndex].id);
  }, [categories]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (categories.length === 0) return;
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      moveToTab((focusedTabIndex + 1) % categories.length);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      moveToTab((focusedTabIndex - 1 + categories.length) % categories.length);
    } else if (e.key === 'Home') {
      e.preventDefault();
      moveToTab(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      moveToTab(categories.length - 1);
    }
  }, [categories, focusedTabIndex, moveToTab]);

  if (categories.length === 0) return null;

  return (
    <div className="w-full mt-12 mb-16">
      <div
        role="tablist"
        aria-label="Plan template categories"
        className="flex items-center pb-2 border-b border-[var(--color-border)] mb-6"
        onKeyDown={handleKeyDown}
      >
        {categories.map((cat, idx) => (
          <button
            key={cat.id}
            ref={el => { tabRefs.current[idx] = el; }}
            role="tab"
            id={`tab-${cat.id}`}
            aria-controls={`panel-${cat.id}`}
            aria-selected={activeTabId === cat.id}
            tabIndex={activeTabId === cat.id ? 0 : -1}
            onClick={() => {
              setActiveTabId(cat.id);
              setFocusedTabIndex(idx);
            }}
            className={`flex items-center justify-center gap-1.5 flex-1 min-w-0 px-1 py-2 text-sm font-medium transition-all border-b-2 -mb-[2px] truncate ${
              activeTabId === cat.id
                ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-main)] hover:border-[var(--color-border)]'
            }`}
          >
            <span className="material-symbols-outlined text-sm shrink-0">{cat.icon}</span>
            <span className="truncate">{cat.name}</span>
          </button>
        ))}
      </div>

      {activeCategory && (
        <div
          role="tabpanel"
          id={`panel-${activeCategory.id}`}
          aria-labelledby={`tab-${activeCategory.id}`}
          className="flex flex-col gap-1"
        >
          {activeCategory.templates.map(template => (
            <Tooltip
              key={template.id}
              content={template.promptTemplate.length > 250 ? template.promptTemplate.substring(0, 250) + '...' : template.promptTemplate}
              position="top"
              className="w-full"
            >
              <button
                onClick={() => onSelectTemplate(template.promptTemplate)}
                className="w-full text-left p-3 hover:bg-[var(--color-surface)] rounded-[var(--radius-lg)] transition-all group flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3"
              >
                <div className="font-bold text-[var(--color-text-main)] text-sm group-hover:text-[var(--color-primary)] transition-colors shrink-0">
                  {template.name}
                </div>
                <div className="text-xs text-[var(--color-text-muted)] truncate">
                  {template.description}
                </div>
              </button>
            </Tooltip>
          ))}
        </div>
      )}
    </div>
  );
};
