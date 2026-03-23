'use client';

import { useState, useMemo } from 'react';
import { Room } from '@/types';
import { IssueEpic } from '@/hooks/useIssues';
import { AgentSummary } from '@/hooks/useAgents';
import { STATUS_COLOR } from '@/lib/constants';
import AgentDashboardTab from './AgentDashboardTab';

type Tab = 'dashboard' | 'config' | 'skills' | 'rooms';

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
  issues: IssueEpic[];
  onBack: () => void;
}

export default function AgentDetail({ agent, rooms, issues, onBack }: AgentDetailProps) {
  const [tab, setTab] = useState<Tab>('dashboard');

  const roleRooms = useMemo(() => {
    return rooms.filter((r) => {
      const activeRole = ROLE_STATUS_MAP[r.status];
      return activeRole === agent.name || r.status === 'passed' || r.status === 'failed-final';
    });
  }, [rooms, agent.name]);

  const agentIssues = useMemo(() => {
    const roomIds = new Set(roleRooms.map((r) => r.room_id));
    return issues.filter((i) => roomIds.has(i.room_id));
  }, [roleRooms, issues]);

  const skillCount = agent.config?.resolved_skills?.length || 0;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'config', label: 'Configuration' },
    { key: 'skills', label: `Skills (${skillCount})` },
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
          <AgentDashboardTab roleRooms={roleRooms} agentIssues={agentIssues} />
        )}
        {tab === 'config' && <ConfigTab agent={agent} />}
        {tab === 'skills' && <SkillsTab agent={agent} />}
        {tab === 'rooms' && <RoomsTab rooms={roleRooms} />}
      </div>
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

function SkillsTab({ agent }: { agent: AgentSummary }) {
  const skills = agent.config?.resolved_skills;

  if (!skills || skills.length === 0) {
    return (
      <div className="empty-state">
        <p>No skills resolved for this role.</p>
      </div>
    );
  }

  const coreSkills = skills.filter((s) => s.trust_level === 'core');
  const experimentalSkills = skills.filter((s) => s.trust_level !== 'core');

  return (
    <div className="skills-tab">
      {coreSkills.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 className="section-title">
            Core
            <span style={{ fontSize: '10px', color: 'var(--green)', marginLeft: '8px', fontWeight: 400 }}>
              {coreSkills.length}
            </span>
          </h3>
          <div className="skills-list">
            {coreSkills.map((s) => (
              <div key={s.name} className="skill-item">
                <span className="skill-name">{s.name}</span>
                <span className="skill-badge skill-badge-core">core</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {experimentalSkills.length > 0 && (
        <div>
          <h3 className="section-title">
            Experimental
            <span style={{ fontSize: '10px', color: 'var(--amber)', marginLeft: '8px', fontWeight: 400 }}>
              {experimentalSkills.length}
            </span>
          </h3>
          <div className="skills-list">
            {experimentalSkills.map((s) => (
              <div key={s.name} className="skill-item">
                <span className="skill-name">{s.name}</span>
                <span className="skill-badge skill-badge-experimental">{s.trust_level}</span>
              </div>
            ))}
          </div>
        </div>
      )}
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
