'use client';

import { useMemo, ReactNode } from 'react';
import { Room } from '@/types';
import { IssueEpic } from '@/hooks/useIssues';
import { ISSUE_STATUS } from '@/lib/issue-utils';
import { BarChart, Bar, XAxis, ResponsiveContainer } from 'recharts';

function ChartCard({
  title,
  subtitle,
  legend,
  children,
}: {
  title: string;
  subtitle: string;
  legend?: { label: string; color: string }[];
  children: ReactNode;
}) {
  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <span className="chart-card-title">{title}</span>
        <span className="chart-card-subtitle">{subtitle}</span>
      </div>
      <div className="chart-card-body">{children}</div>
      {legend && legend.length > 0 && (
        <div className="chart-card-legend">
          {legend.map((l) => (
            <span key={l.label} className="chart-legend-item">
              <span className="chart-legend-dot" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AgentDashboardTab({
  roleRooms,
  agentIssues,
}: {
  roleRooms: Room[];
  agentIssues: IssueEpic[];
}) {
  const chartData = useMemo(() => {
    const days = 14;
    const now = new Date();
    const data = [];

    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dateStr = `${d.getMonth() + 1}/${d.getDate()}`;
      const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      const dayEnd = new Date(dayStart.getTime() + 86400000);

      const dayRooms = roleRooms.filter((r) => {
        if (!r.last_activity) return false;
        const t = new Date(r.last_activity).getTime();
        return t >= dayStart.getTime() && t < dayEnd.getTime();
      });

      const passed = dayRooms.filter((r) => r.status === 'passed').length;
      const failed = dayRooms.filter((r) => r.status === 'failed-final').length;
      const total = passed + failed;
      const successRate = total > 0 ? Math.round((passed / total) * 100) : 0;

      const critical = failed;
      const high = dayRooms.filter((r) => r.status === 'fixing').length;
      const medium = dayRooms.filter(
        (r) => r.status === 'engineering' || r.status === 'qa-review',
      ).length;
      const low = dayRooms.filter((r) => r.status === 'pending').length;

      data.push({
        date: dateStr,
        passed,
        failed,
        done: passed,
        successRate,
        critical,
        high,
        medium,
        low,
      });
    }

    return data;
  }, [roleRooms]);

  const recentIssues = [...agentIssues]
    .sort((a, b) => {
      const refA = parseInt(a.epic_ref.replace(/\D/g, '')) || 0;
      const refB = parseInt(b.epic_ref.replace(/\D/g, '')) || 0;
      return refB - refA;
    })
    .slice(0, 5);

  const tickFormatter = (_value: string, index: number) => {
    if (index === 0 || index === Math.floor(chartData.length / 2) || index === chartData.length - 1)
      return chartData[index]?.date || '';
    return '';
  };

  const axisProps = {
    dataKey: 'date' as const,
    tick: { fill: '#8888aa', fontSize: 9 },
    axisLine: false,
    tickLine: false,
    tickFormatter,
  };

  return (
    <div>
      <div className="chart-cards-grid">
        <ChartCard title="Run Activity" subtitle="Last 14 days">
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={chartData} barGap={1}>
              <XAxis {...axisProps} />
              <Bar dataKey="passed" stackId="a" fill="var(--green)" radius={[1, 1, 0, 0]} />
              <Bar dataKey="failed" stackId="a" fill="var(--red)" radius={[1, 1, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Issues by Priority"
          subtitle="Last 14 days"
          legend={[
            { label: 'Critical', color: 'var(--red)' },
            { label: 'High', color: 'var(--amber)' },
            { label: 'Medium', color: 'var(--green)' },
            { label: 'Low', color: 'var(--purple)' },
          ]}
        >
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={chartData} barGap={1}>
              <XAxis {...axisProps} />
              <Bar dataKey="critical" stackId="a" fill="var(--red)" />
              <Bar dataKey="high" stackId="a" fill="var(--amber)" />
              <Bar dataKey="medium" stackId="a" fill="var(--green)" />
              <Bar dataKey="low" stackId="a" fill="var(--purple)" radius={[1, 1, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Issues by Status"
          subtitle="Last 14 days"
          legend={[{ label: 'Done', color: 'var(--green)' }]}
        >
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={chartData} barGap={1}>
              <XAxis {...axisProps} />
              <Bar dataKey="done" fill="var(--green)" radius={[1, 1, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Success Rate" subtitle="Last 14 days">
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={chartData} barGap={1}>
              <XAxis {...axisProps} />
              <Bar dataKey="successRate" fill="var(--green)" radius={[1, 1, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="recent-issues-section">
        <div className="recent-issues-header">
          <h3 className="section-title" style={{ margin: 0 }}>
            Recent Issues
          </h3>
          <a href="/issues" className="see-all-link">
            See All →
          </a>
        </div>
        {recentIssues.length === 0 ? (
          <div className="empty-state" style={{ padding: '24px' }}>
            <p>No issues for this agent.</p>
          </div>
        ) : (
          <div className="recent-issue-list">
            {recentIssues.map((issue) => {
              const st = ISSUE_STATUS[issue.status];
              return (
                <div key={`${issue.plan_id}-${issue.epic_ref}`} className="recent-issue-row">
                  <span className="recent-issue-ref">{issue.epic_ref}</span>
                  <span className="recent-issue-title">{issue.title}</span>
                  <span
                    className="recent-issue-badge"
                    style={{
                      color: st?.color || 'var(--text-dim)',
                      borderColor: st?.color || 'var(--border)',
                    }}
                  >
                    {st?.label || issue.status}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
