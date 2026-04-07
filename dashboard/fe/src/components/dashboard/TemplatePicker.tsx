import React, { useState, useCallback } from 'react';
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
  const [activeTabId, setActiveTabId] = useState(categories[0]?.id || 'engineering');
  const [focusedTabIndex, setFocusedTabIndex] = useState(0);

  const activeCategory = categories.find(c => c.id === activeTabId);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const next = (focusedTabIndex + 1) % categories.length;
      setFocusedTabIndex(next);
      setActiveTabId(categories[next].id);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prev = (focusedTabIndex - 1 + categories.length) % categories.length;
      setFocusedTabIndex(prev);
      setActiveTabId(categories[prev].id);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setFocusedTabIndex(0);
      setActiveTabId(categories[0].id);
    } else if (e.key === 'End') {
      e.preventDefault();
      setFocusedTabIndex(categories.length - 1);
      setActiveTabId(categories[categories.length - 1].id);
    }
  }, [categories, focusedTabIndex]);

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
            role="tab"
            id={`tab-${cat.id}`}
            aria-controls={`panel-${cat.id}`}
            aria-selected={activeTabId === cat.id}
            tabIndex={activeTabId === cat.id ? 0 : -1}
            onClick={() => { setActiveTabId(cat.id); setFocusedTabIndex(idx); }}
            onFocus={() => setFocusedTabIndex(idx)}
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
