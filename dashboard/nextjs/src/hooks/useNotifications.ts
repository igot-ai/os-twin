'use client';

import { useState, useCallback } from 'react';
import { Notification, WSEvent } from '@/types';
import { apiGet } from '@/lib/api';

export function useNotifications(planId?: string | null) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);

  const loadNotifications = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (planId) params.set('plan_id', planId);
      const data = await apiGet<Notification[] | { notifications: Notification[] }>(
        `/api/notifications?${params.toString()}`
      );
      // Support both array response and {notifications:[]} wrapper
      const items = Array.isArray(data) ? data : (data.notifications || []);
      setNotifications(items);
    } catch (err) {
      console.error('Error fetching global notifications', err);
    }
  }, [planId]);

  const addNotification = useCallback((ev: WSEvent) => {
    const notif: Notification = {
      v: 1,
      id: (ev.entity_id as string) || `ws-${Date.now()}`,
      ts: new Date().toISOString(),
      from: (ev.room?.room_id as string) || 'system',
      to: 'dashboard',
      type: ev.event || 'unknown',
      ref: (ev.room?.task_ref as string) || '',
      body: (ev.content as string) || ev.event || '',
    };
    setNotifications((prev) => [...prev, notif]);
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
