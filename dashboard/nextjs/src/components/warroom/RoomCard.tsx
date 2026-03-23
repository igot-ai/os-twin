'use client';

import { Room } from '@/types';
import { STATUS_COLOR, STATUS_LABEL, PROGRESS_PCT, ACTIVE_STATUSES } from '@/lib/constants';
import { trunc, fmtTime } from '@/lib/utils';

interface RoomCardProps {
  room: Room;
  selected: boolean;
  onClick: () => void;
  onShowDetails?: () => void;
}

// Role icon mapping
function roleIcon(role: string): string {
  if (role.startsWith('engineer')) return '🔧';
  if (role.startsWith('qa') || role.startsWith('tester')) return '🔍';
  if (role.startsWith('architect')) return '📐';
  if (role.startsWith('manager')) return '👤';
  return '⬡';
}

export default function RoomCard({ room, selected, onClick, onShowDetails }: RoomCardProps) {
  const color = STATUS_COLOR[room.status] || '#555';
  const label = STATUS_LABEL[room.status] || room.status.toUpperCase();
  const pct = PROGRESS_PCT[room.status] ?? 0;
  const isActive = ACTIVE_STATUSES.includes(room.status);
  const goalPct = room.goal_total > 0 ? Math.round((room.goal_done / room.goal_total) * 100) : 0;

  const cardStyle: React.CSSProperties = {};
  if (room.status === 'passed') {
    cardStyle.borderColor = color;
    cardStyle.boxShadow = `0 0 18px ${color}44, 0 0 36px ${color}18`;
  } else if (isActive) {
    cardStyle.borderColor = `${color}66`;
    cardStyle.boxShadow = `0 0 10px ${color}22`;
  } else if (room.status === 'failed-final') {
    cardStyle.borderColor = `${color}66`;
    cardStyle.boxShadow = `0 0 10px ${color}22`;
  }

  return (
    <div
      className={`room-card${selected ? ' selected' : ''}`}
      id={`room-${room.room_id}`}
      onClick={onClick}
      style={cardStyle}
      data-status={room.status}
    >
      <div className="rc-head">
        <span className="rc-id">{room.room_id}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {onShowDetails && (
            <button 
              className="rc-details-btn"
              onClick={(e) => { e.stopPropagation(); onShowDetails(); }}
              title="View Extended State"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-dim)',
                cursor: 'pointer',
                padding: '2px',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                opacity: 0.6
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.6')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </button>
          )}
          <span
            className={`rc-chip${isActive ? ' chip-pulse' : ''}`}
            style={{ color, borderColor: `${color}40` }}
          >
            {label}
          </span>
        </div>
      </div>
      <div className="rc-ref">{room.task_ref}</div>
      <div className="rc-desc">{trunc(room.task_description || '', 120)}</div>

      {/* Role badges */}
      {room.roles && room.roles.length > 0 && (
        <div
          className="rc-role-badges"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '3px',
            marginBottom: '4px',
          }}
        >
          {room.roles.map((r, i) => (
            <span
              key={r.instance_id || i}
              style={{
                fontSize: '10px',
                padding: '2px 7px',
                borderRadius: '8px',
                background: 'var(--bg-surface)',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                whiteSpace: 'nowrap',
              }}
              title={r.filename || ''}
            >
              {roleIcon(r.role)} {r.role}
            </span>
          ))}
        </div>
      )}

      <div
        className="rc-goal-stats"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '10px',
          color: 'var(--text-dim)',
          marginBottom: '4px',
        }}
      >
        <span>
          GOALS: {room.goal_done}/{room.goal_total}
        </span>
        <span>{goalPct}%</span>
      </div>

      <div className="rc-bar-wrap">
        <div
          className="rc-bar"
          style={{
            width: `${pct}%`,
            background: color,
            animation: isActive ? 'barPulse 1.5s ease-in-out infinite' : undefined,
          }}
        />
      </div>
      <div className="rc-foot">
        <span style={{ color: 'var(--text-dim)' }}>⬡ {room.message_count}</span>
        {room.retries > 0 && <span style={{ color: '#ff9f43' }}>↻{room.retries}</span>}
        {room.artifact_files && room.artifact_files.length > 0 && (
          <span style={{ color: 'var(--text-dim)' }} title="Artifacts">
            📄{room.artifact_files.length}
          </span>
        )}
        <span style={{ color: 'var(--text-dim)' }}>
          {fmtTime(room.state_changed_at || room.last_activity)}
        </span>
      </div>
    </div>
  );
}
