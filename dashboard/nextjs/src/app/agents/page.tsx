'use client';

import { useState } from 'react';
import { useApp } from '@/contexts/AppContext';
import { useAgents, AgentSummary } from '@/hooks/useAgents';
import AgentList from '@/components/agents/AgentList';
import AgentDetail from '@/components/agents/AgentDetail';

export default function AgentsPage() {
  const { roomList } = useApp();
  const { agents, loading } = useAgents(roomList);
  const [selected, setSelected] = useState<AgentSummary | null>(null);

  if (selected) {
    return (
      <div className="agents-page">
        <AgentDetail agent={selected} rooms={roomList} onBack={() => setSelected(null)} />
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
        <AgentList agents={agents} loading={loading} onSelectAgent={setSelected} />
      </div>
    </div>
  );
}
