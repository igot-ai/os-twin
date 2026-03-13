'use client';

import { Room } from '@/types';
import { STATUS_COLOR, STATUS_LABEL, PROGRESS_PCT, ACTIVE_STATUSES } from '@/lib/constants';
import { trunc, fmtTime } from '@/lib/utils';

interface RoomCardProps {
  room: Room;
  selected: boolean;
  onClick: () => void;
}

export default function RoomCard({ room, selected, onClick }: RoomCardProps) {
  const color = STATUS_COLOR[room.status] || '#555';
  const label = STATUS_LABEL[room.status] || room.status.toUpperCase();
  const pct = PROGRESS_PCT[room.status] ?? 0;
  const isActive = ACTIVE_STATUSES.includes(room.status);
  const goalPct =
    room.goal_total > 0
      ? Math.round((room.goal_done / room.goal_total) * 100)
      : 0;

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
        <span
          className={`rc-chip${isActive ? ' chip-pulse' : ''}`}
          style={{ color, borderColor: `${color}40` }}
        >
          {label}
        </span>
      </div>
      <div className="rc-ref">{room.task_ref}</div>
      <div className="rc-desc">{trunc(room.task_description || '', 90)}</div>

      <div
        className="rc-goal-stats"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '8px',
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
        {room.retries > 0 && (
          <span style={{ color: '#ff9f43' }}>↻{room.retries}</span>
        )}
        <span style={{ color: 'var(--text-dim)' }}>{fmtTime(room.last_activity)}</span>
      </div>
    </div>
  );
}
