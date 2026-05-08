'use client';

/**
 * @deprecated Use EpicEditorPanel instead.
 * This component is retained for backward compatibility only.
 * The new EpicEditorPanel provides tabbed, section-level editing.
 */

import { EpicEditorPanel, EpicEditorPanelProps } from './EpicEditorPanel';

// Re-export the props type for backward compat
export type EpicDetailDrawerProps = EpicEditorPanelProps;

/**
 * Backward-compatible wrapper that delegates to EpicEditorPanel.
 * Existing consumers that import EpicDetailDrawer will automatically
 * get the new tabbed editing experience.
 */
export function EpicDetailDrawer(props: EpicDetailDrawerProps) {
  return <EpicEditorPanel {...props} />;
}
