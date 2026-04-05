import React, { useState, useEffect } from 'react';
import { useWebSocket } from '@/hooks/use-websocket';

interface ActivityEvent {
  id: string;
  type: string;
  timestamp: string;
  message: string;
  link?: string;
  icon?: string;
}

export function ActivityFeed() {
  const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
  const wsUrl = BASE_URL.replace(/^http/, 'ws') + '/ws';
  const { lastMessage } = useWebSocket(wsUrl);

  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [filter, setFilter] = useState<'All' | 'Plans' | 'Agents' | 'System'>('All');

  useEffect(() => {
    if (!lastMessage) return;

    const ts = new Date().toISOString();
    let newEvent: ActivityEvent | null = null;

    if (lastMessage.type === 'epic_progress') {
      newEvent = {
        id: Math.random().toString(36).substr(2, 9),
        type: 'Plans',
        timestamp: ts,
        message: `Epic ${lastMessage.epic_ref} in plan ${lastMessage.plan_id} changed status to ${lastMessage.status} (${lastMessage.progress}%)`,
        link: `/plans/${lastMessage.plan_id}`,
        icon: 'rocket_launch'
      };
    } else if (lastMessage.type === 'connection_health') {
      newEvent = {
        id: Math.random().toString(36).substr(2, 9),
        type: 'System',
        timestamp: ts,
        message: `${lastMessage.service} connection status: ${lastMessage.status}`,
        link: `/settings`,
        icon: 'router'
      };
    } else if (lastMessage.type === 'error') {
      newEvent = {
        id: Math.random().toString(36).substr(2, 9),
        type: 'Agents',
        timestamp: ts,
        message: `Agent error: ${lastMessage.detail}`,
        icon: 'error'
      };
    }

    if (newEvent) {
      setEvents(prev => [newEvent!, ...prev].slice(0, 100)); // Keep last 100
    }
  }, [lastMessage]);

  const filteredEvents = events.filter(e => filter === 'All' || e.type === filter);

  return (
    <div className="flex flex-col h-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-[var(--color-border)]">
        <h3 className="text-xs font-semibold text-[var(--color-text-main)] uppercase tracking-wider">Activity Feed</h3>
        <select 
          className="text-xs bg-transparent border border-[var(--color-border)] rounded px-1 py-0.5 text-[var(--color-text-main)]"
          value={filter}
          onChange={(e) => setFilter(e.target.value as 'All' | 'Plans' | 'Agents' | 'System')}
        >
          <option value="All">All</option>
          <option value="Plans">Plans</option>
          <option value="Agents">Agents</option>
          <option value="System">System</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-6 text-xs text-[var(--color-text-muted)]">
            No recent activity.
          </div>
        ) : (
          filteredEvents.map(event => (
            <div key={event.id} className="flex gap-3 p-2 rounded hover:bg-[var(--color-surface-hover)] transition-colors text-sm">
              <span className="material-symbols-outlined text-[16px] text-[var(--color-text-muted)] mt-0.5">
                {event.icon || 'info'}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[var(--color-text-main)] break-words leading-snug">
                  {event.message}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-[var(--color-text-faint)]">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  {event.link && (
                    <a href={event.link} className="text-[10px] text-[var(--color-primary)] hover:underline">
                      View details
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
