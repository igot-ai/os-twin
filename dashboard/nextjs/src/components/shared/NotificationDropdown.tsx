'use client';

import { Notification } from '@/types';

interface NotificationDropdownProps {
  notifications: Notification[];
  unreadCount: number;
  showDropdown: boolean;
  onToggle: () => void;
  onMarkAllRead: () => void;
}

export default function NotificationDropdown({
  notifications,
  unreadCount,
  showDropdown,
  onToggle,
  onMarkAllRead,
}: NotificationDropdownProps) {
  const getNotificationText = (n: Notification): string => {
    // New schema: {v, id, ts, from, to, type, ref, body}
    const prefix = n.from && n.to ? `${n.from}→${n.to}` : n.from || '';
    const refTag = n.ref ? ` [${n.ref}]` : '';
    return `${prefix}${refTag}: ${n.body || n.type}`;
  };

  return (
    <div className="notification-container">
      <button className="notification-bell" onClick={onToggle}>
        <span className="bell-icon">🔔</span>
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>
      {showDropdown && (
        <div className="notification-dropdown" style={{ display: 'flex' }}>
          <div className="notification-header">
            <span>Notifications</span>
            <button className="mark-read-btn" onClick={onMarkAllRead}>
              Mark all as read
            </button>
          </div>
          <div className="notification-list">
            {notifications.length === 0 ? (
              <div className="empty-notifications">No new notifications</div>
            ) : (
              [...notifications].reverse().map((n, i) => (
                <div key={n.id || i} className="notification-item">
                  <div>{getNotificationText(n)}</div>
                  <div className="notification-time">{new Date(n.ts).toLocaleString()}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
