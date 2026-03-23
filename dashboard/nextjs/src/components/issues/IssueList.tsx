'use client';

import { useState, useMemo } from 'react';
import { Plan } from '@/types';
import { IssueEpic } from '@/hooks/useIssues';
import {
  ISSUE_STATUS,
  getAssignee,
  ASSIGNEE_ICON,
  ALL_STATUSES,
  SortKey,
  GroupKey,
} from '@/lib/issue-utils';

interface IssueListProps {
  issues: IssueEpic[];
  plans: Plan[];
  loading: boolean;
  onSelectIssue: (issue: IssueEpic) => void;
}

export default function IssueList({ issues, plans, loading, onSelectIssue }: IssueListProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [planFilter, setPlanFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortKey>('ref');
  const [groupBy, setGroupBy] = useState<GroupKey>('none');

  const filtered = useMemo(() => {
    let result = issues;

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (i) => i.title.toLowerCase().includes(q) || i.epic_ref.toLowerCase().includes(q),
      );
    }

    if (statusFilter !== 'all') {
      result = result.filter((i) => i.status === statusFilter);
    }

    if (planFilter !== 'all') {
      result = result.filter((i) => i.plan_id === planFilter);
    }

    result = [...result].sort((a, b) => {
      if (sortBy === 'ref') return a.epic_ref.localeCompare(b.epic_ref);
      if (sortBy === 'status') return a.status.localeCompare(b.status);
      if (sortBy === 'title') return a.title.localeCompare(b.title);
      return 0;
    });

    return result;
  }, [issues, search, statusFilter, planFilter, sortBy]);

  const grouped = useMemo(() => {
    if (groupBy === 'none') return [{ key: '', items: filtered }];

    const map = new Map<string, IssueEpic[]>();
    for (const issue of filtered) {
      let key = '';
      if (groupBy === 'plan') key = issue.plan_title || issue.plan_id;
      else if (groupBy === 'status') key = ISSUE_STATUS[issue.status]?.label || issue.status;
      else if (groupBy === 'project') key = issue.working_dir || '.';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(issue);
    }
    return Array.from(map.entries()).map(([key, items]) => ({ key, items }));
  }, [filtered, groupBy]);

  if (loading) {
    return (
      <div className="empty-state">
        <span className="empty-icon">◉</span>
        <p>Loading issues...</p>
      </div>
    );
  }

  return (
    <div className="issue-list">
      <div className="issue-toolbar">
        <input
          className="issue-search"
          type="text"
          placeholder="Search issues..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="issue-filters">
          <select
            className="issue-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {ISSUE_STATUS[s]?.label || s}
              </option>
            ))}
          </select>
          <select
            className="issue-select"
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
          >
            <option value="all">All Plans</option>
            {plans.map((p) => (
              <option key={p.plan_id} value={p.plan_id}>
                {p.title || p.plan_id}
              </option>
            ))}
          </select>
          <select
            className="issue-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortKey)}
          >
            <option value="ref">Sort: Ref</option>
            <option value="status">Sort: Status</option>
            <option value="title">Sort: Title</option>
          </select>
          <select
            className="issue-select"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupKey)}
          >
            <option value="none">No Grouping</option>
            <option value="plan">Group: Plan</option>
            <option value="status">Group: Status</option>
            <option value="project">Group: Project</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">◉</span>
          <p>
            {issues.length === 0
              ? 'No issues yet. Create a plan to generate issues.'
              : 'No issues match the current filters.'}
          </p>
        </div>
      ) : (
        <div className="issue-groups">
          {grouped.map((group) => (
            <div key={group.key || '__all'} className="issue-group">
              {group.key && <div className="issue-group-title">{group.key}</div>}
              <div className="issue-rows">
                {group.items.map((issue) => {
                  const st = ISSUE_STATUS[issue.status];
                  const assignee = getAssignee(issue.status);
                  return (
                    <button
                      key={`${issue.plan_id}-${issue.epic_ref}`}
                      className="issue-row"
                      onClick={() => onSelectIssue(issue)}
                    >
                      <span className="issue-icon" style={{ color: st?.color || 'var(--muted)' }}>
                        {st?.icon || '·'}
                      </span>
                      <span className="issue-ref">{issue.epic_ref}</span>
                      <span className="issue-title">{issue.title}</span>
                      {assignee ? (
                        <span className="issue-assignee">
                          {ASSIGNEE_ICON[assignee] || ''} {assignee}
                        </span>
                      ) : (
                        <span className="issue-assignee issue-assignee-empty">—</span>
                      )}
                      <span className="issue-status" style={{ color: st?.color || 'var(--muted)' }}>
                        {st?.label || issue.status}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
