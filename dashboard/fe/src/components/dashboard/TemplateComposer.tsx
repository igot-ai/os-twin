import React, { useState, useMemo, useRef, useEffect } from 'react';
import type { PromptTemplate, TemplateField, TemplateGroup } from '@/data/prompt-templates';

interface TemplateComposerProps {
  template: PromptTemplate;
  fieldValues: Record<string, string>;
  onFieldChange: (fieldId: string, value: string) => void;
  onFinish: () => void;
  onCancel: () => void;
  completeness: { total: number; filled: number; percent: number };
}

export const TemplateComposer: React.FC<TemplateComposerProps> = ({
  template,
  fieldValues,
  onFieldChange,
  onFinish,
  onCancel,
  completeness,
}) => {
  const groups = template.groups;
  const [activeGroupIdx, setActiveGroupIdx] = useState(0);
  const firstInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  // Focus the first input when a group tab changes
  useEffect(() => {
    const timer = setTimeout(() => firstInputRef.current?.focus(), 80);
    return () => clearTimeout(timer);
  }, [activeGroupIdx]);

  const activeGroup = groups[activeGroupIdx] || groups[0];

  const fieldsForGroup = useMemo(
    () => template.fields.filter(f => f.group === activeGroup?.id),
    [template.fields, activeGroup],
  );

  // Per-group completeness
  const groupCompleteness = useMemo(() => {
    const result: Record<string, { total: number; filled: number }> = {};
    for (const g of groups) {
      const gFields = template.fields.filter(f => f.group === g.id);
      const filled = gFields.filter(f => {
        const val = fieldValues[f.id];
        return val !== undefined && val.trim().length > 0;
      }).length;
      result[g.id] = { total: gFields.length, filled };
    }
    return result;
  }, [groups, template.fields, fieldValues]);

  const canFinish = completeness.filled > 0;
  const requiredRemaining = template.fields
    .filter(f => f.required && !(fieldValues[f.id]?.trim()))
    .length;

  return (
    <div
      className="w-full max-w-2xl mx-auto mt-4 border border-[var(--color-border)] rounded-2xl shadow-[var(--shadow-card)] overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300"
      style={{ background: 'var(--color-surface)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-[var(--color-background)] transition-colors"
            aria-label="Cancel template"
          >
            <span className="material-symbols-outlined text-lg text-[var(--color-text-muted)]">close</span>
          </button>
          <div>
            <h2 className="text-base font-bold text-[var(--color-text-main)]">{template.name}</h2>
            <p className="text-xs text-[var(--color-text-muted)]">{template.description}</p>
          </div>
        </div>

        {/* Progress ring */}
        <div className="flex items-center gap-2">
          <ProgressRingSmall percent={completeness.percent} />
          <span className="text-xs font-medium text-[var(--color-text-muted)]">
            {completeness.filled}/{completeness.total}
          </span>
        </div>
      </div>

      {/* Group tabs */}
      {groups.length > 1 && (
        <div className="flex px-5 pt-3 gap-1 border-b border-[var(--color-border)]">
          {groups.map((g, idx) => {
            const gc = groupCompleteness[g.id];
            const isActive = idx === activeGroupIdx;
            const isDone = gc && gc.filled === gc.total && gc.total > 0;
            return (
              <button
                key={g.id}
                onClick={() => setActiveGroupIdx(idx)}
                className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-all border-b-2 -mb-[1px] ${
                  isActive
                    ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                    : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-main)]'
                }`}
              >
                {isDone && (
                  <span className="material-symbols-outlined text-sm text-[var(--color-success-text)]">check_circle</span>
                )}
                {g.label}
                {gc && gc.total > 0 && !isDone && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--color-background)] text-[var(--color-text-faint)]">
                    {gc.filled}/{gc.total}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Fields */}
      <div className="px-5 py-4 flex flex-col gap-4 max-h-[50vh] overflow-y-auto custom-scrollbar">
        {fieldsForGroup.length === 0 && (
          <p className="text-sm text-[var(--color-text-muted)] text-center py-4">
            No fields in this section.
          </p>
        )}
        {fieldsForGroup.map((field, idx) => (
          <FieldInput
            key={field.id}
            field={field}
            value={fieldValues[field.id] || ''}
            onChange={(val) => onFieldChange(field.id, val)}
            ref={idx === 0 ? firstInputRef : undefined}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--color-border)] bg-[var(--color-background)]">
        <div className="text-xs text-[var(--color-text-faint)]">
          {requiredRemaining > 0
            ? `${requiredRemaining} required field${requiredRemaining > 1 ? 's' : ''} remaining`
            : 'All required fields filled'}
        </div>
        <div className="flex items-center gap-2">
          {groups.length > 1 && activeGroupIdx < groups.length - 1 && (
            <button
              onClick={() => setActiveGroupIdx(prev => prev + 1)}
              className="px-3 py-1.5 text-sm font-medium rounded-lg border border-[var(--color-border)] text-[var(--color-text-main)] hover:bg-[var(--color-surface)] transition-colors"
            >
              Next
              <span className="material-symbols-outlined text-sm ml-1 align-middle">arrow_forward</span>
            </button>
          )}
          <button
            onClick={onFinish}
            disabled={!canFinish}
            className="px-4 py-1.5 text-sm font-medium rounded-lg bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm">send</span>
            Use template
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const FieldInput = React.forwardRef<
  HTMLInputElement | HTMLTextAreaElement,
  {
    field: TemplateField;
    value: string;
    onChange: (val: string) => void;
  }
>(({ field, value, onChange }, ref) => {
  const inputClasses =
    'w-full rounded-lg px-3 py-2 text-sm bg-[var(--color-background)] border border-[var(--color-border)] text-[var(--color-text-main)] placeholder:text-[var(--color-text-faint)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-muted)] focus:border-[var(--color-primary)] transition-all';

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-[var(--color-text-main)] flex items-center gap-1">
        {field.label}
        {field.required && <span className="text-[var(--color-danger,#ef4444)] text-xs">*</span>}
      </label>
      {field.hint && (
        <p className="text-xs text-[var(--color-text-faint)]">{field.hint}</p>
      )}
      {field.type === 'long' ? (
        <textarea
          ref={ref as React.Ref<HTMLTextAreaElement>}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.hint || ''}
          className={`${inputClasses} resize-none`}
          rows={3}
        />
      ) : field.type === 'checklist' && field.options ? (
        <div className="flex flex-wrap gap-2">
          {field.options.map((opt) => {
            const selected = value.split(',').map(v => v.trim()).includes(opt);
            return (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const current = value.split(',').map(v => v.trim()).filter(Boolean);
                  const next = selected
                    ? current.filter(v => v !== opt)
                    : [...current, opt];
                  onChange(next.join(', '));
                }}
                className={`px-3 py-1.5 text-xs rounded-full border transition-all ${
                  selected
                    ? 'border-[var(--color-primary)] bg-[var(--color-primary-muted)] text-[var(--color-primary)] font-medium'
                    : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)] hover:text-[var(--color-text-main)]'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      ) : (
        <input
          ref={ref as React.Ref<HTMLInputElement>}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.hint || ''}
          className={inputClasses}
        />
      )}
    </div>
  );
});

FieldInput.displayName = 'FieldInput';

function ProgressRingSmall({ percent }: { percent: number }) {
  const r = 14;
  const stroke = 3;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <svg width={36} height={36} viewBox="0 0 36 36" className="transform -rotate-90">
      <circle
        cx={18}
        cy={18}
        r={r}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth={stroke}
      />
      <circle
        cx={18}
        cy={18}
        r={r}
        fill="none"
        stroke={percent === 100 ? 'var(--color-success-text)' : 'var(--color-primary)'}
        strokeWidth={stroke}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-500"
      />
    </svg>
  );
}
