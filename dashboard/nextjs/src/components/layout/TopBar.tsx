'use client';

import Image from 'next/image';
import NotificationDropdown from '@/components/shared/NotificationDropdown';
import { Notification } from '@/types';

interface TopBarProps {
  summary: {
    active: number;
    passed: number;
    total: number;
  };
  connected: boolean;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onOpenSkills: () => void;
  // Notifications
  notifications: Notification[];
  unreadCount: number;
  showNotifications: boolean;
  onToggleNotifications: () => void;
  onMarkAllRead: () => void;
}

export default function TopBar({
  summary,
  connected,
  theme,
  onToggleTheme,
  onOpenSettings,
  onOpenSkills,
  notifications,
  unreadCount,
  showNotifications,
  onToggleNotifications,
  onMarkAllRead,
}: TopBarProps) {
  const connClass = connected ? 'connected' : 'disconnected';
  const connText = connected ? 'LIVE' : 'RECONNECTING...';

  return (
    <header className="topbar">
      <div className="topbar-logo">
        <Image
          src="/assets/logo.svg"
          className="logo-img"
          alt="OS Twin AI"
          width={20}
          height={20}
        />
        <span className="logo-text">
          OS<span className="logo-accent">Twin</span>
        </span>
        <span className="logo-version">v0.1.0</span>
      </div>

      <div className="topbar-stats">
        <div className="stat-pill" id="stat-active">
          <span className="stat-dot active-dot"></span>
          <span id="stat-active-text">{summary.active} active</span>
        </div>
        <div className="stat-pill" id="stat-passed">
          <span className="stat-icon">✓</span>
          <span id="stat-passed-text">{summary.passed} passed</span>
        </div>
        <div className="stat-pill" id="stat-rooms">
          <span className="stat-icon">⬡</span>
          <span id="stat-rooms-text">{summary.total} rooms</span>
        </div>
      </div>

      <div className="topbar-conn">
        <NotificationDropdown
          notifications={notifications}
          unreadCount={unreadCount}
          showDropdown={showNotifications}
          onToggle={onToggleNotifications}
          onMarkAllRead={onMarkAllRead}
        />
        <span id="conn-dot" className={`conn-dot ${connClass}`}></span>
        <span
          id="conn-status"
          style={{
            color: connected ? '#00ff8888' : '#ff6b6b88',
          }}
        >
          {connText}
        </span>
        <button className="topbar-skills-btn" onClick={onOpenSkills} title="Skills Registry">
          <span>◆</span> SKILLS
        </button>
        <button className="theme-toggle" onClick={onOpenSettings} title="Settings">
          <span>⚙</span>
        </button>
        <button className="theme-toggle" onClick={onToggleTheme}>
          <span>{theme === 'dark' ? '🌙' : '☀️'}</span>
        </button>
      </div>
    </header>
  );
}
