'use client';

import { useEffect, useCallback, useState } from 'react';
import { WSEvent, Message } from '@/types';
import { apiGet } from '@/lib/api';

// Hooks
import { useWebSocket } from '@/hooks/useWebSocket';
import { useRooms } from '@/hooks/useRooms';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { useNotifications } from '@/hooks/useNotifications';
import { usePlanRefine } from '@/hooks/usePlanRefine';

// Layout components
import AuthOverlay from '@/components/shared/AuthOverlay';
import TopBar from '@/components/layout/TopBar';
import PipelineBar from '@/components/layout/PipelineBar';
import ReleaseBar from '@/components/layout/ReleaseBar';

import PlanLauncher from '@/components/panels/PlanLauncher';
import WarRoomGrid from '@/components/panels/WarRoomGrid';
import ChannelFeed from '@/components/panels/ChannelFeed';
import PlanEditor from '@/components/plan/PlanEditor';
import SettingsPanel from '@/components/panels/SettingsPanel';
import SkillsPanel from '@/components/panels/SkillsPanel';
import ExtendedStatePanel from '@/components/panels/ExtendedStatePanel';

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const { showLogin, error: authError, performLogin } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const {
    rooms,
    roomList,
    summary,
    feedMessages,
    channelFilter,
    activePlanId,
    selectRoom,
    clearFeed,
    loadInitialRooms,
    loadPlanRooms,
    handleWSEvent,
  } = useRooms();

  const [activeExtendedRoomId, setActiveExtendedRoomId] = useState<string | null>(null);

  const {
    notifications,
    unreadCount,
    showDropdown: showNotifications,
    loadNotifications,
    addNotification,
    markAllRead,
    toggleDropdown: toggleNotifications,
  } = useNotifications(activePlanId);

  usePlanRefine(); // Keep hook active

  const [activeEditorPlanId, setActiveEditorPlanId] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftWidth, setLeftWidth] = useState(220);
  const [rightWidth, setRightWidth] = useState(380);

  const onLeftDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const capturedStartW = leftWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX;
      const newW = Math.max(48, Math.min(480, capturedStartW + delta));
      setLeftWidth(newW);
      setLeftCollapsed(newW <= 48);
    };
    const onUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [leftWidth]);

  const onRightDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const capturedStartW = rightWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX;
      const newW = Math.max(48, Math.min(700, capturedStartW + delta));
      setRightWidth(newW);
      setRightCollapsed(newW <= 48);
    };
    const onUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [rightWidth]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const match = path.match(/^\/plans\/([a-zA-Z0-9]+)/);
      if (match) {
        setActiveEditorPlanId(match[1]);
      }
    }
  }, []);

  const [releaseContent, setReleaseContent] = useState<string | null>(null);

  const onWSMessage = useCallback(
    (ev: WSEvent) => {
      handleWSEvent(ev);
      addNotification(ev);
      if (ev.event === 'release' && ev.content) {
        setReleaseContent(ev.content as string);
        celebrate();
      }
    },
    [handleWSEvent, addNotification]
  );

  const { connected } = useWebSocket(onWSMessage);

  useEffect(() => {
    loadNotifications();
    apiGet<{ available: boolean; content: string | null }>('/api/release').then((data) => {
      if (data.available && data.content) {
        setReleaseContent(data.content);
      }
    });
  }, [loadNotifications]);

  useEffect(() => {
    if (activePlanId) {
      loadNotifications();
    }
  }, [activePlanId, loadNotifications]);

  const selectedRoom = channelFilter ? rooms[channelFilter] || null : null;

  if (!mounted) return null;

  return (
    <>
      <AuthOverlay show={showLogin} onLogin={performLogin} error={authError} />

      <TopBar
        summary={summary}
        connected={connected}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenSettings={() => setShowSettings(true)}
        onOpenSkills={() => setShowSkills(true)}
        notifications={notifications}
        unreadCount={unreadCount}
        showNotifications={showNotifications}
        onToggleNotifications={toggleNotifications}
        onMarkAllRead={markAllRead}
      />

      <PipelineBar rooms={roomList} />

      <main className="main-layout" style={{ display: 'flex' }}>
        <PlanLauncher
          onPlanSelected={loadPlanRooms}
          isCollapsed={leftCollapsed}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          style={{ width: leftCollapsed ? 48 : leftWidth, minWidth: leftCollapsed ? 48 : leftWidth }}
        />

        <div className="resize-handle resize-handle-left" onMouseDown={onLeftDragStart} />

        <WarRoomGrid
          rooms={roomList}
          summary={summary}
          channelFilter={channelFilter}
          onSelectRoom={selectRoom}
          onShowDetails={(roomId) => setActiveExtendedRoomId(roomId)}
          style={{ flex: 1 }}
        />

        <div className="resize-handle resize-handle-right" onMouseDown={onRightDragStart} />

        <ChannelFeed
          feedMessages={feedMessages}
          channelFilter={channelFilter}
          selectedRoom={selectedRoom}
          activePlanId={activePlanId}
          onClearFeed={clearFeed}
          isCollapsed={rightCollapsed}
          onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
          style={{ width: rightCollapsed ? 48 : rightWidth, minWidth: rightCollapsed ? 48 : rightWidth }}
        />
      </main>

      {releaseContent && (
        <ReleaseBar content={releaseContent} />
      )}

      {activeEditorPlanId && (
        <PlanEditor
          planId={activeEditorPlanId}
          onClose={() => {
            setActiveEditorPlanId(null);
            window.history.pushState({}, '', '/');
          }}
          onPlanSaved={loadInitialRooms}
        />
      )}

      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
      {showSkills && <SkillsPanel onClose={() => setShowSkills(false)} />}
      {activeExtendedRoomId && (
        <ExtendedStatePanel
          roomId={activeExtendedRoomId}
          onClose={() => setActiveExtendedRoomId(null)}
        />
      )}
    </>
  );
}

// Celebration particles
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
