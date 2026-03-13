'use client';

import { useEffect, useCallback, useState } from 'react';
import { WSEvent } from '@/types';
import { apiGet } from '@/lib/api';

// Hooks
import { useWebSocket } from '@/hooks/useWebSocket';
import { useRooms } from '@/hooks/useRooms';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { useNotifications } from '@/hooks/useNotifications';

// Layout components
import AuthOverlay from '@/components/shared/AuthOverlay';
import TopBar from '@/components/layout/TopBar';
import PipelineBar from '@/components/layout/PipelineBar';
import ReleaseBar from '@/components/layout/ReleaseBar';

// Panel components
import PlanLauncher from '@/components/panels/PlanLauncher';
import WarRoomGrid from '@/components/panels/WarRoomGrid';
import ChannelFeed from '@/components/panels/ChannelFeed';

export default function Dashboard() {
  const { showLogin, error: authError, performLogin } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const {
    notifications,
    unreadCount,
    showDropdown: showNotifications,
    loadNotifications,
    addNotification,
    markAllRead,
    toggleDropdown: toggleNotifications,
  } = useNotifications();

  const {
    rooms,
    roomList,
    summary,
    feedMessages,
    channelFilter,
    selectRoom,
    clearFeed,
    loadInitialRooms,
    handleWSEvent,
  } = useRooms();

  const [releaseContent, setReleaseContent] = useState<string | null>(null);

  // Combined WS handler that updates rooms + notifications + release
  const onWSMessage = useCallback(
    (ev: WSEvent) => {
      handleWSEvent(ev);
      addNotification(ev);

      if (ev.event === 'release' && ev.content) {
        setReleaseContent(ev.content as string);
        celebrate();
      }

      if (ev.event === 'plans_updated') {
        // PlanLauncher handles its own reload
      }
    },
    [handleWSEvent, addNotification]
  );

  const { connected } = useWebSocket(onWSMessage);

  // Initial load
  useEffect(() => {
    loadInitialRooms();
    loadNotifications();

    // Load release
    apiGet<{ available: boolean; content: string | null }>('/api/release').then((data) => {
      if (data.available && data.content) {
        setReleaseContent(data.content);
      }
    });
  }, [loadInitialRooms, loadNotifications]);

  const selectedRoom = channelFilter ? rooms[channelFilter] || null : null;

  return (
    <>
      <AuthOverlay show={showLogin} onLogin={performLogin} error={authError} />

      <TopBar
        summary={summary}
        connected={connected}
        theme={theme}
        onToggleTheme={toggleTheme}
        notifications={notifications}
        unreadCount={unreadCount}
        showNotifications={showNotifications}
        onToggleNotifications={toggleNotifications}
        onMarkAllRead={markAllRead}
      />

      <PipelineBar rooms={roomList} />

      <main className="main-layout">
        <PlanLauncher />

        <WarRoomGrid
          rooms={roomList}
          summary={summary}
          channelFilter={channelFilter}
          onSelectRoom={selectRoom}
        />

        <ChannelFeed
          feedMessages={feedMessages}
          channelFilter={channelFilter}
          selectedRoom={selectedRoom}
          onClearFeed={clearFeed}
        />
      </main>

      <ReleaseBar content={releaseContent} />
    </>
  );
}

// Celebration particles (ported from app.js)
function celebrate() {
  const items = ['🎉', '✅', '🚀', '⬡', '★', '◆', '✦'];
  for (let i = 0; i < 14; i++) {
    setTimeout(() => spawnParticle(items[i % items.length]), i * 90);
  }
}

function spawnParticle(emoji: string) {
  const el = document.createElement('span');
  Object.assign(el.style, {
    position: 'fixed',
    left: `${Math.random() * 100}vw`,
    top: `${40 + Math.random() * 30}vh`,
    fontSize: `${14 + Math.random() * 20}px`,
    opacity: '1',
    pointerEvents: 'none',
    zIndex: '9999',
    transition: 'transform 1.6s ease-out, opacity 1.6s ease-out',
    userSelect: 'none',
  });
  el.textContent = emoji;
  document.body.appendChild(el);

  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      el.style.transform = `translateY(-${120 + Math.random() * 200}px) rotate(${(Math.random() - 0.5) * 60}deg)`;
      el.style.opacity = '0';
    })
  );
  setTimeout(() => el.remove(), 2000);
}
