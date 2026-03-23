'use client';

import { createContext, useContext, useCallback, useState, useEffect } from 'react';
import { WSEvent, Room, Notification } from '@/types';
import { RoomMsg } from '@/hooks/useRooms';
import { apiGet } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useRooms } from '@/hooks/useRooms';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { useNotifications } from '@/hooks/useNotifications';
import { usePlanRefine } from '@/hooks/usePlanRefine';

export interface AppContextType {
  showLogin: boolean;
  authError: string;
  performLogin: (apiKey: string) => Promise<boolean>;

  theme: 'dark' | 'light';
  toggleTheme: () => void;

  connected: boolean;

  notifications: Notification[];
  unreadCount: number;
  showNotifications: boolean;
  toggleNotifications: () => void;
  markAllRead: () => void;
  loadNotifications: () => void;

  rooms: Record<string, Room>;
  roomList: Room[];
  summary: {
    total: number;
    active: number;
    passed: number;
    failed: number;
    pending: number;
    qa: number;
    eng: number;
  };
  allMessages: RoomMsg[];
  feedMessages: RoomMsg[];
  channelFilter: string | null;
  activePlanId: string | null;
  selectRoom: (roomId: string) => void;
  clearFeed: () => void;
  loadInitialRooms: () => Promise<void>;
  loadPlanRooms: (planId: string | null) => Promise<void>;

  chatHistory: { role: 'user' | 'assistant'; content: string }[];
  isRefining: boolean;
  streamedResponse: string;
  refineError: string | null;
  refine: (message: string, planContent?: string, planId?: string) => Promise<void>;
  cancelRefine: () => void;
  clearRefineHistory: () => void;

  releaseContent: string | null;

  openPlanEditor: (planId: string) => void;
  closePlanEditor: () => void;
  activeEditorPlanId: string | null;
}

const AppContext = createContext<AppContextType | null>(null);

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { showLogin, error: authError, performLogin } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const {
    rooms,
    roomList,
    summary,
    allMessages,
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
  const {
    chatHistory,
    isRefining,
    streamedResponse,
    error: refineError,
    refine,
    cancelRefine,
    clearHistory,
  } = usePlanRefine();

  const [releaseContent, setReleaseContent] = useState<string | null>(null);
  const [activeEditorPlanId, setActiveEditorPlanId] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      const match = window.location.pathname.match(/^\/plans\/([a-zA-Z0-9]+)/);
      if (match) return match[1];
    }
    return null;
  });

  const openPlanEditor = useCallback((planId: string) => {
    setActiveEditorPlanId(planId);
    window.history.pushState({}, '', `/plans/${planId}`);
  }, []);

  const closePlanEditor = useCallback(() => {
    setActiveEditorPlanId(null);
    window.history.pushState({}, '', window.location.pathname);
  }, []);

  const onWSMessage = useCallback(
    (ev: WSEvent) => {
      handleWSEvent(ev);
      addNotification(ev);
      if (ev.event === 'release' && ev.content) {
        setReleaseContent(ev.content as string);
        celebrate();
      }
    },
    [handleWSEvent, addNotification],
  );

  const { connected } = useWebSocket(onWSMessage);

  useEffect(() => {
    loadNotifications();
    apiGet<{ available: boolean; content: string | null }>('/api/release').then((data) => {
      if (data.available && data.content) setReleaseContent(data.content);
    });
  }, [loadNotifications]);

  useEffect(() => {
    if (activePlanId) loadNotifications();
  }, [activePlanId, loadNotifications]);

  const value: AppContextType = {
    showLogin,
    authError,
    performLogin,
    theme,
    toggleTheme,
    connected,
    notifications,
    unreadCount,
    showNotifications,
    toggleNotifications,
    markAllRead,
    loadNotifications,
    rooms,
    roomList,
    summary,
    allMessages,
    feedMessages,
    channelFilter,
    activePlanId,
    selectRoom,
    clearFeed,
    loadInitialRooms,
    loadPlanRooms,
    chatHistory,
    isRefining,
    streamedResponse,
    refineError,
    refine,
    cancelRefine,
    clearRefineHistory: clearHistory,
    releaseContent,
    openPlanEditor,
    closePlanEditor,
    activeEditorPlanId,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

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
    }),
  );
  setTimeout(() => el.remove(), 2000);
}
