'use client';

import { useState, useCallback } from 'react';
import { Room, Message, Notification, WSEvent } from '@/types';
import { apiGet } from '@/lib/api';

interface RoomMsg {
  roomId: string;
  msg: Message;
}

/** Convert a Notification (new schema) into a RoomMsg for the feed. */
function notifToRoomMsg(roomId: string, n: Notification): RoomMsg {
  return {
    roomId,
    msg: {
      id: n.id,
      ts: n.ts,
      from: n.from,
      to: n.to,
      type: n.type as Message['type'],
      ref: n.ref,
      body: n.body,
    },
  };
}

/** Fetch notifications for a room and convert them to RoomMsgs. */
async function loadRoomNotifications(roomId: string): Promise<RoomMsg[]> {
  try {
    const data = await apiGet<Notification[] | { notifications: Notification[] }>(
      `/api/notifications?room_id=${roomId}&limit=50`
    );
    const items = Array.isArray(data) ? data : (data.notifications || []);
    return items.map((n) => notifToRoomMsg(roomId, n));
  } catch {
    return [];
  }
}

export function useRooms() {
  const [rooms, setRooms] = useState<Record<string, Room>>({});
  const [allMessages, setAllMessages] = useState<RoomMsg[]>([]);
  const [channelFilter, setChannelFilter] = useState<string | null>(null);

  const loadInitialRooms = useCallback(async () => {
    try {
      const data = await apiGet<{ rooms: Room[] }>('/api/rooms');
      const roomMap: Record<string, Room> = {};
      for (const room of data.rooms || []) {
        roomMap[room.room_id] = room;
      }
      setRooms(roomMap);

      // Load channel history, falling back to notifications
      const msgs: RoomMsg[] = [];
      for (const room of data.rooms || []) {
        try {
          const chData = await apiGet<{ messages: Message[] }>(
            `/api/rooms/${room.room_id}/channel`
          );
          const channelMsgs = chData.messages || [];
          if (channelMsgs.length > 0) {
            for (const m of channelMsgs) {
              msgs.push({ roomId: room.room_id, msg: m });
            }
          } else {
            // Fall back to notifications for this room
            const notifMsgs = await loadRoomNotifications(room.room_id);
            msgs.push(...notifMsgs);
          }
        } catch {
          // Try notifications as fallback
          const notifMsgs = await loadRoomNotifications(room.room_id);
          msgs.push(...notifMsgs);
        }
      }
      setAllMessages(msgs);
    } catch (err) {
      console.error('Failed to load initial rooms:', err);
    }
  }, []);

  /** Load plan-scoped war-rooms (replaces the room grid). */
  const loadPlanRooms = useCallback(async (planId: string | null) => {
    if (!planId) {
      // Reset to global rooms
      await loadInitialRooms();
      return;
    }

    try {
      const data = await apiGet<{ rooms: Room[]; warrooms_dir?: string }>(
        `/api/plans/${planId}/rooms`
      );
      const planRooms = data.rooms || [];
      const roomMap: Record<string, Room> = {};
      for (const room of planRooms) {
        roomMap[room.room_id] = room;
      }
      setRooms(roomMap);
      setChannelFilter(null);

      // Load channel history for plan rooms, falling back to notifications
      const msgs: RoomMsg[] = [];
      for (const room of planRooms) {
        try {
          const chData = await apiGet<{ messages: Message[] }>(
            `/api/rooms/${room.room_id}/channel`
          );
          const channelMsgs = chData.messages || [];
          if (channelMsgs.length > 0) {
            for (const m of channelMsgs) {
              msgs.push({ roomId: room.room_id, msg: m });
            }
          } else {
            const notifMsgs = await loadRoomNotifications(room.room_id);
            msgs.push(...notifMsgs);
          }
        } catch {
          const notifMsgs = await loadRoomNotifications(room.room_id);
          msgs.push(...notifMsgs);
        }
      }
      setAllMessages(msgs);
    } catch (err) {
      console.error('Failed to load plan rooms:', err);
    }
  }, [loadInitialRooms]);

  const handleWSEvent = useCallback((ev: WSEvent) => {
    switch (ev.event) {
      case 'room_created':
        if (ev.room) {
          setRooms((prev) => ({ ...prev, [ev.room!.room_id]: ev.room! }));
          setAllMessages((prev) => [
            ...prev,
            {
              roomId: ev.room!.room_id,
              msg: {
                type: 'task',
                from_: 'manager',
                to: 'engineer',
                ref: ev.room!.task_ref,
                body: `War-room opened: ${ev.room!.room_id}`,
                ts: ev.room!.last_activity || '',
              } as Message,
            },
          ]);
        }
        break;

      case 'room_updated':
        if (ev.room) {
          setRooms((prev) => ({ ...prev, [ev.room!.room_id]: ev.room! }));
          if (ev.new_messages?.length) {
            setAllMessages((prev) => {
              const newMsgs: RoomMsg[] = ev.new_messages!.map((m) => ({
                roomId: ev.room!.room_id,
                msg: m,
              }));
              const updated = [...prev, ...newMsgs];
              return updated.length > 600 ? updated.slice(-600) : updated;
            });
          }
        }
        break;

      case 'room_removed':
        if (ev.room_id) {
          setRooms((prev) => {
            const next = { ...prev };
            delete next[ev.room_id!];
            return next;
          });
        }
        break;
    }
  }, []);

  const selectRoom = useCallback(
    (roomId: string) => {
      setChannelFilter((prev) => (prev === roomId ? null : roomId));
    },
    []
  );

  const clearFeed = useCallback(() => {
    setAllMessages([]);
  }, []);

  // Compute summary
  const roomList = Object.values(rooms);
  const summary = {
    total: roomList.length,
    active: roomList.filter((r) =>
      ['engineering', 'qa-review', 'fixing'].includes(r.status)
    ).length,
    passed: roomList.filter((r) => r.status === 'passed').length,
    failed: roomList.filter((r) => r.status === 'failed-final').length,
    pending: roomList.filter((r) => r.status === 'pending').length,
    qa: roomList.filter((r) => r.status === 'qa-review').length,
    eng: roomList.filter((r) => r.status === 'engineering').length,
  };

  // Filtered messages
  const feedMessages = channelFilter
    ? allMessages.filter((m) => m.roomId === channelFilter)
    : allMessages;

  return {
    rooms,
    roomList,
    summary,
    allMessages,
    feedMessages,
    channelFilter,
    selectRoom,
    clearFeed,
    loadInitialRooms,
    loadPlanRooms,
    handleWSEvent,
  };
}

