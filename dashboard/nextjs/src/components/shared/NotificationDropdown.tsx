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
    const data = n.data as Record<string, unknown>;
    switch (n.event_type) {
      case 'room_created': {
        const room = data.room as Record<string, unknown> | undefined;
        return `War-room created: ${room?.room_id || 'Unknown'}`;
      }
      case 'room_updated': {
        const room = data.room as Record<string, unknown> | undefined;
        return `Room updated: ${room?.room_id || 'Unknown'}`;
      }
      case 'room_action':
        return `Room action: ${data.action} in ${data.room_id}`;
      case 'reaction_toggled':
        return `Reaction toggled in ${data.room_id || ''}`;
      case 'comment_published':
        return `New comment in ${data.room_id || ''}`;
      default:
        return `${n.event_type}`;
    }
  };

  return (
    <div className="notification-container">
      <button className="notification-bell" onClick={onToggle}>
        <span className="bell-icon">🔔</span>
        {unreadCount > 0 && (
          <span className="notification-badge">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
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
              [...notifications]
                .reverse()
                .map((n, i) => (
                  <div key={i} className="notification-item">
                    <div>{getNotificationText(n)}</div>
                    <div className="notification-time">
                      {new Date(n.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
