'use client';

import { AgentSummary } from '@/hooks/useAgents';

interface AgentListProps {
  agents: AgentSummary[];
  loading: boolean;
  onSelectAgent: (agent: AgentSummary) => void;
}

export default function AgentList({ agents, loading, onSelectAgent }: AgentListProps) {
  if (loading) {
    return (
      <div className="empty-state">
        <span className="empty-icon">⚙</span>
        <p>Loading agents...</p>
      </div>
    );
  }

  return (
    <div className="agent-list">
      {agents.map((agent) => (
        <button key={agent.name} className="agent-row" onClick={() => onSelectAgent(agent)}>
          <span className="agent-icon">{agent.icon}</span>
          <span className="agent-name">{agent.name}</span>
          <span className={`agent-status-badge agent-status-${agent.status}`}>
            {agent.status === 'running' ? 'Running' : 'Idle'}
          </span>
          <span className="agent-rooms">
            {agent.activeRooms > 0
              ? `${agent.activeRooms} active room${agent.activeRooms !== 1 ? 's' : ''}`
              : 'No active rooms'}
          </span>
          {agent.lastActivity && (
            <span className="agent-last">{formatRelativeTime(agent.lastActivity)}</span>
          )}
        </button>
      ))}
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
