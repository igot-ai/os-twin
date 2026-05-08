/**
 * Epic Stats Computation (EPIC-003)
 *
 * Computes per-EPIC progress stats from a parsed EpicDocument,
 * used by DAGViewer to display progress bars, DoD counts,
 * AC warning badges, and description tooltips on DAG canvas nodes.
 */

import { EpicDocument } from './epic-parser';

/** Per-epic stats computed from parsedPlan */
export interface EpicStats {
  tasksDone: number;
  tasksTotal: number;
  dodDone: number;
  dodTotal: number;
  hasAC: boolean;
  description: string;
}

/**
 * Compute task/DoD/AC stats for each epic in the parsedPlan document.
 *
 * Walks all sections of each epic and:
 * - Counts total and completed tasks from 'tasklist' sections
 * - Counts total and checked DoD items from 'checklist' sections
 *   whose heading contains "definition of done" or "dod"
 * - Determines if AC exists from 'checklist' sections whose heading
 *   contains "acceptance criteria" or "ac"
 * - Extracts the description from 'text' sections whose heading
 *   contains "description"
 *
 * Returns a Map keyed by epic ref (e.g. "EPIC-001").
 */
export function computeEpicStats(parsedPlan: EpicDocument | null): Map<string, EpicStats> {
  const statsMap = new Map<string, EpicStats>();
  if (!parsedPlan) return statsMap;

  for (const epic of parsedPlan.epics) {
    let tasksDone = 0;
    let tasksTotal = 0;
    let dodDone = 0;
    let dodTotal = 0;
    let hasAC = false;
    let description = '';

    for (const section of epic.sections) {
      if (section.type === 'tasklist' && section.tasks) {
        tasksTotal += section.tasks.length;
        tasksDone += section.tasks.filter(t => t.completed).length;
      }
      if (section.type === 'checklist' && section.items) {
        const headingLower = section.heading.toLowerCase();
        if (headingLower.includes('definition of done') || headingLower.includes('dod')) {
          dodTotal += section.items.length;
          dodDone += section.items.filter(i => i.checked).length;
        }
        if (headingLower.includes('acceptance criteria') || headingLower.includes('ac')) {
          hasAC = section.items.length > 0;
        }
      }
      if (section.type === 'text' && section.heading.toLowerCase().includes('description')) {
        description = section.content.trim();
      }
    }

    statsMap.set(epic.ref, { tasksDone, tasksTotal, dodDone, dodTotal, hasAC, description });
  }
  return statsMap;
}
