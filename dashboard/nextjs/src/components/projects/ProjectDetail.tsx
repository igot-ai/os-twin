'use client';

import { useState } from 'react';
import { Project, Epic } from '@/types';
import { apiGet } from '@/lib/api';
import { IssueEpic } from '@/hooks/useIssues';
import IssueList from '@/components/issues/IssueList';
import IssueDetail from '@/components/issues/IssueDetail';

const PROJECT_COLORS = [
  'var(--purple)',
  'var(--cyan)',
  'var(--green)',
  'var(--amber)',
  'var(--orange)',
  'var(--red)',
  '#6ee7b7',
  '#93c5fd',
];

type Tab = 'plans' | 'issues' | 'config';

interface ProjectDetailProps {
  project: Project;
  colorIndex: number;
  onBack: () => void;
  onOpenPlan?: (planId: string) => void;
}

export default function ProjectDetail({
  project,
  colorIndex,
  onBack,
  onOpenPlan,
}: ProjectDetailProps) {
  const [tab, setTab] = useState<Tab>('plans');
  const [issues, setIssues] = useState<IssueEpic[]>([]);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<IssueEpic | null>(null);

  async function loadIssues() {
    setIssuesLoading(true);
    const allIssues: IssueEpic[] = [];
    for (const plan of project.plans) {
      try {
        const data = await apiGet<{ epics?: Epic[] }>(`/api/plans/${plan.plan_id}`);
        if (data.epics) {
          allIssues.push(...data.epics.map((epic) => ({ ...epic, plan_title: plan.title })));
        }
      } catch {
        /* skip */
      }
    }
    setIssues(allIssues);
    setIssuesLoading(false);
  }

  function switchTab(t: Tab) {
    setTab(t);
    if (t === 'issues' && issues.length === 0) loadIssues();
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'plans', label: 'Plans' },
    { key: 'issues', label: 'Issues' },
    { key: 'config', label: 'Configuration' },
  ];

  return (
    <div className="project-detail">
      <button className="breadcrumb-back" onClick={onBack}>
        ← Projects
      </button>

      <div className="project-detail-header">
        <span
          className="project-dot project-dot-lg"
          style={{ background: PROJECT_COLORS[colorIndex % PROJECT_COLORS.length] }}
        />
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>
            {project.name}
          </h1>
          <span className="project-path-dim">{project.path}</span>
        </div>
      </div>

      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab-btn${tab === t.key ? ' active' : ''}`}
            onClick={() => switchTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === 'plans' && <PlansTab project={project} onOpenPlan={onOpenPlan} />}
        {tab === 'issues' &&
          (selectedIssue ? (
            <IssueDetail issue={selectedIssue} onBack={() => setSelectedIssue(null)} />
          ) : (
            <IssueList
              issues={issues}
              plans={project.plans}
              loading={issuesLoading}
              onSelectIssue={setSelectedIssue}
            />
          ))}
        {tab === 'config' && <ConfigTab project={project} />}
      </div>
    </div>
  );
}

function PlansTab({
  project,
  onOpenPlan,
}: {
  project: Project;
  onOpenPlan?: (planId: string) => void;
}) {
  const statusColor: Record<string, string> = {
    draft: 'var(--text-dim)',
    launched: 'var(--cyan)',
    completed: 'var(--green)',
    active: 'var(--cyan)',
  };

  return (
    <div className="plans-tab">
      {project.plans.length === 0 ? (
        <div className="empty-state">
          <p>No plans in this project yet.</p>
        </div>
      ) : (
        <div className="plan-rows">
          {project.plans.map((plan) => (
            <button
              key={plan.plan_id}
              className="plan-row"
              onClick={() => onOpenPlan?.(plan.plan_id)}
            >
              <span className="plan-row-title">{plan.title || 'Untitled'}</span>
              <span
                className="plan-row-status"
                style={{ color: statusColor[plan.status] || 'var(--text-dim)' }}
              >
                {plan.status}
              </span>
              <span className="plan-row-epics">
                {plan.epic_count} epic{plan.epic_count !== 1 ? 's' : ''}
              </span>
              <span className="plan-row-date">
                {new Date(plan.created_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ConfigTab({ project }: { project: Project }) {
  return (
    <div className="config-tab">
      <div className="config-field">
        <span className="config-label">Working Directory</span>
        <code className="config-value">{project.path}</code>
      </div>
      <div className="config-field">
        <span className="config-label">Plans</span>
        <span className="config-value">{project.planCount}</span>
      </div>
      <div className="config-field">
        <span className="config-label">Total Epics</span>
        <span className="config-value">{project.epicCount}</span>
      </div>
      {project.plans.length > 0 && (
        <div className="config-field">
          <span className="config-label">War-Rooms Directory</span>
          <code className="config-value">
            {project.plans[0].warrooms_dir || `${project.path}/.war-rooms`}
          </code>
        </div>
      )}
    </div>
  );
}
