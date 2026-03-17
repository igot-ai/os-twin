'use client';

import { useEffect, useCallback, useState, useRef } from 'react';
import { WSEvent } from '@/types';
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

export default function Dashboard() {
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

  const {
    notifications,
    unreadCount,
    showDropdown: showNotifications,
    loadNotifications,
    addNotification,
    markAllRead,
    toggleDropdown: toggleNotifications,
  } = useNotifications(activePlanId);

  const { refine, cancelRefine, clearHistory } = usePlanRefine(); // Added this hook call

  const [activeEditorPlanId, setActiveEditorPlanId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState<string>(''); // State to hold editor content
  const [aiError, setAiError] = useState<string | null>(null); // State to hold AI error
  const [showSettings, setShowSettings] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  // Resizable panel widths
  const [leftWidth, setLeftWidth] = useState(220);
  const [rightWidth, setRightWidth] = useState(380);

  // Drag handlers — each uses private closure state, no shared refs
  const onLeftDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    let startW = 0;
    // Read current left width from state via setter pattern
    setLeftWidth(w => { startW = w; return w; });
    // Use a local captured value for the drag
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leftWidth]);

  const onRightDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const capturedStartW = rightWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: MouseEvent) => {
      // drag handle LEFT = increase right panel width
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rightWidth]);

  // Path detection for /plans/abc
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

  // Initial load — rooms are loaded by PlanLauncher (auto-selects active plan)
  useEffect(() => {
    loadNotifications();

    // Load release
    apiGet<{ available: boolean; content: string | null }>('/api/release').then((data) => {
      if (data.available && data.content) {
        setReleaseContent(data.content);
      }
    });
  }, [loadNotifications]);

  // Reload notifications when active plan changes
  useEffect(() => {
    if (activePlanId) {
      loadNotifications();
    }
  }, [activePlanId, loadNotifications]);

  const selectedRoom = channelFilter ? rooms[channelFilter] || null : null;

  // Placeholder for handleApplyAI, assuming it will be defined elsewhere or passed down
  const handleApplyAI = useCallback((content: string) => {
    // Logic to apply AI content to the editor
    setEditorContent(content);
  }, []);

  return (
    <>
      <AuthOverlay show={showLogin} onLogin={performLogin} error={authError} />

      <TopBar
        summary={summary}
        connected={connected}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenSettings={() => setShowSettings(true)}
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
          onToggleCollapse={() => {
            if (leftCollapsed) { setLeftCollapsed(false); setLeftWidth(220); }
            else { setLeftCollapsed(true); setLeftWidth(48); }
          }}
          style={{ width: leftCollapsed ? 48 : leftWidth, flexShrink: 0 }}
        />

        {/* Left drag handle */}
        <div
          className="resize-handle resize-handle-left"
          onMouseDown={onLeftDragStart}
          title="Drag to resize"
        />

        <WarRoomGrid
          rooms={roomList}
          summary={summary}
          channelFilter={channelFilter}
          onSelectRoom={selectRoom}
          style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}
        />

        {/* Right drag handle */}
        <div
          className="resize-handle resize-handle-right"
          onMouseDown={onRightDragStart}
          title="Drag to resize"
        />

        <ChannelFeed
          feedMessages={feedMessages}
          channelFilter={channelFilter}
          selectedRoom={selectedRoom}
          activePlanId={activePlanId}
          onClearFeed={clearFeed}
          isCollapsed={rightCollapsed}
          onToggleCollapse={() => {
            if (rightCollapsed) { setRightCollapsed(false); setRightWidth(380); }
            else { setRightCollapsed(true); setRightWidth(48); }
          }}
          style={{ width: rightCollapsed ? 48 : rightWidth, flexShrink: 0 }}
        />
      </main>

      {activeEditorPlanId && (
        <PlanEditor
          planId={activeEditorPlanId}
          onClose={() => {
            setActiveEditorPlanId(null);
            window.history.pushState({}, '', '/');
          }}
        />
      )}

      <ReleaseBar content={releaseContent} />

      {showSettings && (
        <SettingsPanel onClose={() => setShowSettings(false)} />
      )}
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
