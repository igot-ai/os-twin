'use client';

import { useEffect, useRef } from 'react';
import { Notification } from '@/types';

interface NotificationDropdownProps {
  notifications: Notification[];
  unreadCount: number;
  showDropdown: boolean;
  onToggle: () => void;
  onMarkAllRead: () => void;
  onClose?: () => void;
}

export default function NotificationDropdown({
  notifications,
  unreadCount,
  showDropdown,
  onToggle,
  onMarkAllRead,
  onClose,
}: NotificationDropdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showDropdown) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose?.();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showDropdown, onClose]);

  const getNotificationText = (n: Notification): string => {
    // New schema: {v, id, ts, from, to, type, ref, body}
    const prefix = n.from && n.to ? `${n.from}→${n.to}` : n.from || '';
    const refTag = n.ref ? ` [${n.ref}]` : '';
    return `${prefix}${refTag}: ${n.body || n.type}`;
  };

  return (
    <div className="notification-container" ref={containerRef}>
      <button id="notification-bell" className="notification-bell" onClick={onToggle}>
        <span className="bell-icon">🔔</span>
        {unreadCount > 0 && (
          <span id="notification-badge" className="notification-badge">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      <div
        id="notification-dropdown"
        className="notification-dropdown"
        style={{ display: showDropdown ? 'flex' : 'none' }}
      >
        <div className="notification-header">
          <span>Notifications</span>
          <button className="mark-read-btn" onClick={onMarkAllRead}>
            Mark all as read
          </button>
        </div>
        <div id="global-notification-list" className="notification-list">
          {notifications.length === 0 ? (
            <div className="empty-notifications">No new notifications</div>
          ) : (
            [...notifications]
              .reverse()
              .map((n, i) => (
                <div key={n.id || i} className="notification-item">
                  <div>{getNotificationText(n)}</div>
                  <div className="notification-time">
                    {n.ts}
                  </div>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
