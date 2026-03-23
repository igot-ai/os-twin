'use client';

import { Suspense, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useApp } from '@/contexts/AppContext';
import { useAgents } from '@/hooks/useAgents';
import { useIssues } from '@/hooks/useIssues';
import AgentList from '@/components/agents/AgentList';
import AgentDetail from '@/components/agents/AgentDetail';

export default function AgentsPage() {
  return (
    <Suspense>
      <AgentsPageInner />
    </Suspense>
  );
}

function AgentsPageInner() {
  const { roomList } = useApp();
  const { agents, loading } = useAgents(roomList);
  const { issues } = useIssues();
  const searchParams = useSearchParams();
  const router = useRouter();
  const role = searchParams.get('role');

  const selected = useMemo(() => {
    if (!role) return null;
    return agents.find((a) => a.name === role) || null;
  }, [role, agents]);

  if (selected) {
    return (
      <div className="agents-page">
        <AgentDetail
          agent={selected}
          rooms={roomList}
          issues={issues}
          onBack={() => router.push('/agents')}
        />
      </div>
    );
  }

  return (
    <div className="agents-page">
      <div className="page-header">
        <h1 className="page-title">Agents</h1>
        <span className="page-subtitle">
          {agents.filter((a) => a.status === 'running').length} running ·{' '}
          {agents.filter((a) => a.status === 'idle').length} idle
        </span>
      </div>
      <div style={{ padding: '12px 20px' }}>
        <AgentList
          agents={agents}
          loading={loading}
          onSelectAgent={(agent) => router.push(`/agents?role=${agent.name}`)}
        />
      </div>
    </div>
  );
}
