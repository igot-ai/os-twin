'use client';

import { useState, useCallback } from 'react';
import { Room, Message, WSEvent } from '@/types';
import { apiGet } from '@/lib/api';

interface RoomMsg {
  roomId: string;
  msg: Message;
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

      // Load channel history
      const msgs: RoomMsg[] = [];
      for (const room of data.rooms || []) {
        try {
          const chData = await apiGet<{ messages: Message[] }>(
            `/api/rooms/${room.room_id}/channel`
          );
          for (const m of chData.messages || []) {
            msgs.push({ roomId: room.room_id, msg: m });
          }
        } catch {
          // skip room
        }
      }
      setAllMessages(msgs);
    } catch (err) {
      console.error('Failed to load initial rooms:', err);
    }
  }, []);

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
    handleWSEvent,
  };
}
