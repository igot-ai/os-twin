import React from 'react';

interface TemplateProgressProps {
  templateName: string;
  total: number;
  filled: number;
  percent: number;
  unfilledLabels: string[];
  onEdit: () => void;
  onClear: () => void;
}

export const TemplateProgress: React.FC<TemplateProgressProps> = ({
  templateName,
  total,
  filled,
  percent,
  unfilledLabels,
  onEdit,
  onClear,
}) => {
  if (total === 0) return null;

  const isDone = percent === 100;

  return (
    <div className="w-full max-w-2xl mx-auto mt-2 px-1 animate-in fade-in duration-200">
      <div className="flex items-center gap-3">
        {/* Progress bar */}
        <div className="flex-1 flex items-center gap-2">
          <div className="flex items-center gap-1.5 shrink-0">
            <span
              className="material-symbols-outlined text-sm"
              style={{ color: isDone ? 'var(--color-success-text)' : 'var(--color-primary)' }}
            >
              {isDone ? 'check_circle' : 'edit_note'}
            </span>
            <span className="text-xs font-medium text-[var(--color-text-muted)] truncate max-w-[140px]">
              {templateName}
            </span>
          </div>

          <div className="flex-1 h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${percent}%`,
                background: isDone ? 'var(--color-success-text)' : 'var(--color-primary)',
              }}
            />
          </div>

          <span className="text-[11px] font-medium text-[var(--color-text-faint)] shrink-0 tabular-nums">
            {filled}/{total}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onEdit}
            className="p-1 rounded hover:bg-[var(--color-surface)] transition-colors"
            aria-label="Edit template fields"
            title="Edit fields"
          >
            <span className="material-symbols-outlined text-sm text-[var(--color-text-muted)]">tune</span>
          </button>
          <button
            onClick={onClear}
            className="p-1 rounded hover:bg-[var(--color-surface)] transition-colors"
            aria-label="Clear template"
            title="Clear template"
          >
            <span className="material-symbols-outlined text-sm text-[var(--color-text-muted)]">close</span>
          </button>
        </div>
      </div>

      {/* Unfilled hint (collapsed by default, shown when < 50%) */}
      {!isDone && unfilledLabels.length > 0 && percent < 50 && (
        <div className="mt-1 text-[10px] text-[var(--color-text-faint)] truncate">
          Still needed: {unfilledLabels.slice(0, 3).join(', ')}
          {unfilledLabels.length > 3 && ` +${unfilledLabels.length - 3} more`}
        </div>
      )}
    </div>
  );
};
