'use client';

import { useApp } from '@/contexts/AppContext';
import { STATUS_COLOR } from '@/lib/constants';

export default function DashboardPage() {
  const { roomList, summary, activePlanId } = useApp();

  const statusGroups = [
    { label: 'Active', value: summary.active, color: 'var(--cyan)' },
    { label: 'Passed', value: summary.passed, color: 'var(--green)' },
    { label: 'Failed', value: summary.failed, color: 'var(--red)' },
    { label: 'Pending', value: summary.pending, color: 'var(--amber)' },
    { label: 'Total', value: summary.total, color: 'var(--text-dim)' },
  ];

  const recentRooms = [...roomList]
    .sort((a, b) => (b.last_activity || '').localeCompare(a.last_activity || ''))
    .slice(0, 10);

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        {activePlanId && <span className="page-subtitle">Plan: {activePlanId}</span>}
      </div>

      <div className="dashboard-stats">
        {statusGroups.map((s) => (
          <div key={s.label} className="dash-stat-card">
            <div className="dash-stat-value" style={{ color: s.color }}>
              {s.value}
            </div>
            <div className="dash-stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="dashboard-section">
        <h2 className="section-title">Recent Rooms</h2>
        {recentRooms.length === 0 ? (
          <div className="empty-state">
            <span className="empty-icon">⬡</span>
            <p>
              No active rooms. Launch a plan from <strong>War Rooms</strong> to get started.
            </p>
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
                <span className="room-list-progress">
                  {room.goal_done}/{room.goal_total}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
