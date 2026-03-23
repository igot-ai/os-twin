import { RoomStatus } from '@/types';

export const ISSUE_STATUS: Record<string, { label: string; icon: string; color: string }> = {
  pending: { label: 'Pending', icon: '○', color: 'var(--amber)' },
  engineering: { label: 'In Progress', icon: '↑', color: 'var(--cyan)' },
  'qa-review': { label: 'In Review', icon: '●', color: 'var(--purple)' },
  fixing: { label: 'Fixing', icon: '↓', color: 'var(--orange)' },
  passed: { label: 'Done', icon: '✓', color: 'var(--green)' },
  'failed-final': { label: 'Failed', icon: '✗', color: 'var(--red)' },
  paused: { label: 'Paused', icon: '⏸', color: 'var(--muted)' },
};

export function getAssignee(status: string): string | null {
  if (status === 'engineering' || status === 'fixing') return 'Engineer';
  if (status === 'qa-review') return 'QA';
  return null;
}

export const ASSIGNEE_ICON: Record<string, string> = {
  Engineer: '⚙',
  QA: '✦',
};

export type SortKey = 'ref' | 'status' | 'title';
export type GroupKey = 'none' | 'plan' | 'status' | 'project';

export const ALL_STATUSES: RoomStatus[] = [
  'pending',
  'engineering',
  'qa-review',
  'fixing',
  'passed',
  'failed-final',
  'paused',
];
