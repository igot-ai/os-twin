'use client';

import React from 'react';
import { useStats } from '@/hooks/use-stats';
import MetricCard from './MetricCard';

export default function StatsRow() {
  const { stats, isLoading, isError } = useStats();

  if (isError) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="p-5 rounded-xl border border-border bg-surface text-center">
             <span className="text-xs text-text-muted">Failed to load stats</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
      <MetricCard
        label="Total Plans"
        value={stats?.total_plans?.value ?? 0}
        trend={stats?.total_plans?.trend ?? { direction: 'flat', delta: 0 }}
        color="#2563eb"
        icon="description"
        isLoading={isLoading}
      />
      <MetricCard
        label="Active EPICs"
        value={stats?.active_epics?.value ?? 0}
        trend={stats?.active_epics?.trend ?? { direction: 'flat', delta: 0 }}
        color="#8b5cf6"
        icon="rocket_launch"
        isLoading={isLoading}
      />
      <MetricCard
        label="Completion Rate"
        value={stats?.completion_rate?.value ?? 0}
        trend={stats?.completion_rate?.trend ?? { direction: 'flat', delta: 0 }}
        color="#10b981"
        icon="check_circle"
        suffix="%"
        isLoading={isLoading}
      />
      <MetricCard
        label="Escalations"
        value={stats?.escalations?.value ?? 0}
        trend={stats?.escalations?.trend ?? { direction: 'flat', delta: 0 }}
        color="#ef4444"
        icon="warning"
        isLoading={isLoading}
      />
    </div>
  );
}
