'use client';

import { useState, useCallback } from 'react';
import { Notification, WSEvent } from '@/types';
import { apiGet } from '@/lib/api';

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);

  const loadNotifications = useCallback(async () => {
    try {
      const data = await apiGet<{ notifications: Notification[] }>(
        '/api/notifications?limit=50'
      );
      setNotifications(data.notifications || []);
    } catch (err) {
      console.error('Error fetching global notifications', err);
    }
  }, []);

  const addNotification = useCallback((ev: WSEvent) => {
    setNotifications((prev) => [
      ...prev,
      {
        event_type: ev.event,
        data: ev as Record<string, unknown>,
        timestamp: new Date().toISOString(),
      },
    ]);
    setUnreadCount((prev) => prev + 1);
  }, []);

  const markAllRead = useCallback(() => {
    setUnreadCount(0);
  }, []);

  const toggleDropdown = useCallback(() => {
    setShowDropdown((prev) => {
      if (!prev) {
        setUnreadCount(0);
      }
      return !prev;
    });
  }, []);

  return {
    notifications,
    unreadCount,
    showDropdown,
    setShowDropdown,
    loadNotifications,
    addNotification,
    markAllRead,
    toggleDropdown,
  };
}
