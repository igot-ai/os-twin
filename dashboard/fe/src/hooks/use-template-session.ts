import { useState, useCallback, useMemo } from 'react';
import {
  computeCompleteness,
  hydrateTemplate,
  ensureFieldsExtracted,
  type PromptTemplate,
} from '@/data/prompt-templates';

export interface TemplateSession {
  /** The currently selected template, or null if freeform mode. */
  template: PromptTemplate | null;
  /** Per-field values keyed by field id (field-0, field-1, ...). */
  fieldValues: Record<string, string>;
  /** Completeness metrics for the active template. */
  completeness: {
    total: number;
    filled: number;
    percent: number;
    unfilledLabels: string[];
  };
  /** The hydrated prompt text (template + filled values). */
  hydratedPrompt: string;
  /** Whether the user is currently in composer mode. */
  isComposerOpen: boolean;
  /** Select a template and open the composer. */
  selectTemplate: (t: PromptTemplate) => void;
  /** Update a single field value. */
  setFieldValue: (fieldId: string, value: string) => void;
  /** Close the composer and inject the hydrated prompt into the textarea. */
  finishComposer: () => string;
  /** Discard the template and return to freeform mode. */
  clearTemplate: () => void;
  /** Open composer for an already-selected template. */
  openComposer: () => void;
  /** Update completeness from raw textarea content (for freeform editing). */
  computeFromText: (text: string) => {
    total: number;
    filled: number;
    percent: number;
    unfilledLabels: string[];
  };
}

const EMPTY_COMPLETENESS = { total: 0, filled: 0, percent: 100, unfilledLabels: [] as string[] };

export function useTemplateSession(): TemplateSession {
  const [template, setTemplate] = useState<PromptTemplate | null>(null);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  const hydratedPrompt = useMemo(() => {
    if (!template) return '';
    return hydrateTemplate(template.promptTemplate, fieldValues);
  }, [template, fieldValues]);

  const completeness = useMemo(() => {
    if (!template) return EMPTY_COMPLETENESS;
    return computeCompleteness(template.promptTemplate, hydratedPrompt);
  }, [template, hydratedPrompt]);

  const selectTemplate = useCallback((t: PromptTemplate) => {
    setTemplate(ensureFieldsExtracted(t));
    setFieldValues({});
    setIsComposerOpen(true);
  }, []);

  const setFieldValue = useCallback((fieldId: string, value: string) => {
    setFieldValues(prev => ({ ...prev, [fieldId]: value }));
  }, []);

  const finishComposer = useCallback(() => {
    setIsComposerOpen(false);
    return hydratedPrompt;
  }, [hydratedPrompt]);

  const clearTemplate = useCallback(() => {
    setTemplate(null);
    setFieldValues({});
    setIsComposerOpen(false);
  }, []);

  const openComposer = useCallback(() => {
    if (template) setIsComposerOpen(true);
  }, [template]);

  const computeFromText = useCallback(
    (text: string) => {
      if (!template) return EMPTY_COMPLETENESS;
      return computeCompleteness(template.promptTemplate, text);
    },
    [template],
  );

  return {
    template,
    fieldValues,
    completeness,
    hydratedPrompt,
    isComposerOpen,
    selectTemplate,
    setFieldValue,
    finishComposer,
    clearTemplate,
    openComposer,
    computeFromText,
  };
}
