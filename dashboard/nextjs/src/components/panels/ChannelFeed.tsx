'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { Room, Message, Notification } from '@/types';
import { STATUS_COLOR, PROGRESS_PCT } from '@/lib/constants';
import { fmtTime, trunc } from '@/lib/utils';
import { apiGet, apiFetch } from '@/lib/api';

// Inline FeedMessage to avoid extra file since it's small
function FeedMessage({ roomId, msg }: { roomId: string; msg: Message }) {
  const icon =
    {
      task: '📋',
      done: '✓',
      review: '🔍',
      pass: '✅',
      fail: '✗',
      fix: '🔧',
      signoff: '✍',
      release: '🚀',
      error: '⚠',
    }[msg.type] || '·';

  const from = msg.from_ || msg.from || '?';
  const to = msg.to || '?';

  return (
    <div className={`feed-msg feed-${msg.type || 'unknown'}`}>
      <span className="fm-time">{fmtTime(msg.ts)}</span>
      <span className="fm-route">
        {from}→{to}
      </span>
      <span className={`fm-type t-${msg.type}`}>
        {icon} {msg.type || ''}
      </span>
      {msg.ref && <span className="fm-ref">[{msg.ref}]</span>}
      <span className="fm-body">{trunc(msg.body || '', 130)}</span>
    </div>
  );
}

// Room Detail sub-component
function RoomDetail({ room, planId }: { room: Room; planId: string | null }) {
  const [activityLogs, setActivityLogs] = useState<Notification[]>([]);

  const color = STATUS_COLOR[room.status] || '#555';
  const pct = PROGRESS_PCT[room.status] ?? 0;
  const isActive = ['engineering', 'qa-review', 'fixing'].includes(room.status);

  useEffect(() => {
    const loadLogs = async () => {
      try {
        const data = await apiGet<Notification[] | { notifications: Notification[] }>(
          `/api/notifications?plan_id=${planId || ''}&room_id=${room.room_id}&limit=20`
        );
        // Support both array response and {notifications:[]} wrapper
        const items = Array.isArray(data) ? data : (data.notifications || []);
        setActivityLogs(items);
      } catch {
        // ignore
      }
    };
    loadLogs();
  }, [room.room_id, room.status, planId]);

  const roomAction = async (action: string) => {
    try {
      await apiFetch(`/api/rooms/${room.room_id}/action?action=${action}`, {
        method: 'POST',
      });
    } catch (e) {
      console.error(`Failed to ${action} room:`, e);
    }
  };

  // Parse goals from task_description
  const goals =
    room.task_description?.match(/- \[[ xX\-!]+\] .+/g)?.map((t) => {
      const checked = t.includes('[x]') || t.includes('[X]');
      const failed = t.includes('[-]') || t.includes('[!]');
      const text = t.replace(/- \[[ xX\-!]+\] /, '');
      return { text, checked, failed };
    }) || [];

  return (
    <div className="room-detail" style={{ display: 'block' }}>
      <div className="detail-header">
        <div className="detail-header-top">
          <div className="detail-room-id">{room.room_id}</div>
          <div className="room-actions">
            {(room.status === 'paused' || room.status === 'failed-final') && (
              <button className="action-btn-mini start" onClick={() => roomAction('start')}>
                start
              </button>
            )}
            {isActive && (
              <button className="action-btn-mini" onClick={() => roomAction('pause')}>
                pause
              </button>
            )}
            {room.status === 'paused' && (
              <button className="action-btn-mini" onClick={() => roomAction('resume')}>
                resume
              </button>
            )}
            {['engineering', 'qa-review', 'fixing', 'paused', 'pending'].includes(room.status) && (
              <button className="action-btn-mini stop" onClick={() => roomAction('stop')}>
                stop
              </button>
            )}
          </div>
        </div>
        <div className="detail-task-ref">{room.task_ref}</div>
      </div>
      <div className="detail-progress">
        <div className="rc-bar-wrap">
          <div className="rc-bar" style={{ width: `${pct}%`, background: color }} />
        </div>
      </div>
      <div className="detail-goals">
        <label className="field-label">Goal Checklist</label>
        <div className="goal-list">
          {goals.map((g, i) => (
            <div key={i} className="goal-item">
              <span
                className={`goal-checkbox${g.checked ? ' checked' : ''}${g.failed ? ' failed' : ''}`}
              >
                {g.checked ? '✓' : g.failed ? '✗' : ''}
              </span>
              <span className="goal-text">{g.text}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="detail-activity">
        <label className="field-label">Activity Log</label>
        <div className="activity-log">
          {activityLogs.length === 0 ? (
            <div style={{ padding: '10px', color: 'var(--text-dim)' }}>No activity recorded.</div>
          ) : (
            [...activityLogs].reverse().map((entry, i) => (
              <div key={entry.id || i} className="activity-item">
                <span className="activity-ts">{fmtTime(entry.ts)}</span>
                <span className="activity-event">
                  {entry.from}→{entry.to}
                </span>
                <span className="activity-type">
                  {String(entry.type).replace(/_/g, ' ')}
                </span>
                {entry.ref && <span className="activity-ref">[{entry.ref}]</span>}
                {entry.body && (
                  <span className="activity-body">{trunc(entry.body, 80)}</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
      <div className="detail-divider" />
      <label className="field-label">Messages</label>
    </div>
  );
}

interface ChannelFeedProps {
  feedMessages: { roomId: string; msg: Message }[];
  channelFilter: string | null;
  selectedRoom: Room | null;
  activePlanId: string | null;
  onClearFeed: () => void;
}

export default function ChannelFeed({
  feedMessages,
  channelFilter,
  selectedRoom,
  activePlanId,
  onClearFeed,
}: ChannelFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedMessages.length]);

  return (
    <aside className="panel panel-right">
      <div className="panel-header">
        <span className="panel-title">
          {channelFilter ? `▸ ${channelFilter}` : '▸ CHANNEL FEED'}
        </span>
        <button className="clear-btn" onClick={onClearFeed}>
          clear
        </button>
      </div>

      <div className="panel-body">
        {selectedRoom && <RoomDetail room={selectedRoom} planId={activePlanId} />}

        <div className="feed" ref={feedRef}>
          {feedMessages.length === 0 ? (
            <div className="feed-empty">Waiting for messages...</div>
          ) : (
            feedMessages.map((m, i) => (
              <FeedMessage key={i} roomId={m.roomId} msg={m.msg} />
            ))
          )}
        </div>
      </div>
    </aside>
  );
}
