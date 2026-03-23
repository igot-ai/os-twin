'use client';

import { useState, useMemo } from 'react';
import { Room } from '@/types';
import { AgentSummary } from '@/hooks/useAgents';
import { STATUS_COLOR } from '@/lib/constants';

type Tab = 'dashboard' | 'config' | 'rooms';

const ROLE_STATUS_MAP: Record<string, string> = {
  engineering: 'engineer',
  fixing: 'engineer',
  'qa-review': 'qa',
  'architect-review': 'architect',
  'manager-triage': 'manager',
  pending: 'manager',
};

interface AgentDetailProps {
  agent: AgentSummary;
  rooms: Room[];
  onBack: () => void;
}

export default function AgentDetail({ agent, rooms, onBack }: AgentDetailProps) {
  const [tab, setTab] = useState<Tab>('dashboard');

  const roleRooms = useMemo(() => {
    return rooms.filter((r) => {
      const activeRole = ROLE_STATUS_MAP[r.status];
      return activeRole === agent.name || r.status === 'passed' || r.status === 'failed-final';
    });
  }, [rooms, agent.name]);

  const activeRooms = roleRooms.filter((r) => ROLE_STATUS_MAP[r.status] === agent.name);
  const passed = roleRooms.filter((r) => r.status === 'passed').length;
  const failed = roleRooms.filter((r) => r.status === 'failed-final').length;
  const total = passed + failed;
  const successRate = total > 0 ? Math.round((passed / total) * 100) : 0;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'config', label: 'Configuration' },
    { key: 'rooms', label: 'Rooms' },
  ];

  return (
    <div className="agent-detail">
      <button className="breadcrumb-back" onClick={onBack}>
        ← Agents
      </button>

      <div className="agent-detail-header">
        <span className="agent-detail-icon">{agent.icon}</span>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>
            {agent.name}
          </h1>
          <span className="agent-detail-sub">
            {agent.config?.default_model || 'Unknown model'}
            {' · '}
            Timeout: {agent.config?.timeout_seconds || 600}s
          </span>
        </div>
        <span className={`agent-status-badge agent-status-${agent.status}`}>
          {agent.status === 'running' ? 'Running' : 'Idle'}
        </span>
      </div>

      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab-btn${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === 'dashboard' && (
          <DashboardTab
            activeRooms={activeRooms}
            passed={passed}
            failed={failed}
            successRate={successRate}
            roleRooms={roleRooms}
          />
        )}
        {tab === 'config' && <ConfigTab agent={agent} />}
        {tab === 'rooms' && <RoomsTab rooms={roleRooms} />}
      </div>
    </div>
  );
}

function DashboardTab({
  activeRooms,
  passed,
  failed,
  successRate,
  roleRooms,
}: {
  activeRooms: Room[];
  passed: number;
  failed: number;
  successRate: number;
  roleRooms: Room[];
}) {
  const stats = [
    { label: 'Active', value: activeRooms.length, color: 'var(--cyan)' },
    { label: 'Completed', value: passed, color: 'var(--green)' },
    { label: 'Failed', value: failed, color: 'var(--red)' },
    { label: 'Success Rate', value: `${successRate}%`, color: 'var(--text)' },
  ];

  const recentRooms = [...roleRooms]
    .sort((a, b) => (b.last_activity || '').localeCompare(a.last_activity || ''))
    .slice(0, 8);

  return (
    <div>
      <div className="dashboard-stats" style={{ padding: '12px 0' }}>
        {stats.map((s) => (
          <div key={s.label} className="dash-stat-card">
            <div className="dash-stat-value" style={{ color: s.color }}>
              {s.value}
            </div>
            <div className="dash-stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <h3 className="section-title">Recent Rooms</h3>
      {recentRooms.length === 0 ? (
        <div className="empty-state" style={{ padding: '24px' }}>
          <p>No room history for this role.</p>
        </div>
      ) : (
        <div className="room-list">
          {recentRooms.map((room) => (
            <div key={room.room_id} className="room-list-row">
              <span
                className="room-status-dot"
                style={{ background: STATUS_COLOR[room.status] || '#555' }}
              />
              <span className="room-list-id">{room.room_id}</span>
              <span className="room-list-ref">{room.task_ref}</span>
              <span
                className="room-list-status"
                style={{ color: STATUS_COLOR[room.status] || 'var(--text-dim)' }}
              >
                {room.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConfigTab({ agent }: { agent: AgentSummary }) {
  const cfg = agent.config;
  if (!cfg) {
    return (
      <div className="empty-state">
        <p>No configuration available.</p>
      </div>
    );
  }

  const fields = [
    { label: 'Model', value: cfg.default_model },
    { label: 'Timeout', value: `${cfg.timeout_seconds}s` },
    { label: 'Description', value: cfg.description },
    { label: 'Capabilities', value: cfg.capabilities?.join(', ') || '—' },
    { label: 'Task Types', value: cfg.supported_task_types?.join(', ') || '—' },
  ];

  return (
    <div className="config-tab">
      {fields.map((f) => (
        <div key={f.label} className="config-field">
          <span className="config-label">{f.label}</span>
          <span className="config-value">{f.value}</span>
        </div>
      ))}
    </div>
  );
}

function RoomsTab({ rooms }: { rooms: Room[] }) {
  if (rooms.length === 0) {
    return (
      <div className="empty-state">
        <p>No rooms associated with this role.</p>
      </div>
    );
  }

  const sorted = [...rooms].sort((a, b) =>
    (b.last_activity || '').localeCompare(a.last_activity || ''),
  );

  return (
    <div className="room-list">
      {sorted.map((room) => (
        <div key={room.room_id} className="room-list-row">
          <span
            className="room-status-dot"
            style={{ background: STATUS_COLOR[room.status] || '#555' }}
          />
          <span className="room-list-id">{room.room_id}</span>
          <span className="room-list-ref">{room.task_ref}</span>
          <span
            className="room-list-status"
            style={{ color: STATUS_COLOR[room.status] || 'var(--text-dim)' }}
          >
            {room.status}
          </span>
          <span className="room-list-progress">
            {room.goal_done}/{room.goal_total}
          </span>
        </div>
      ))}
    </div>
  );
}
