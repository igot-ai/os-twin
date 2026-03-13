'use client';

import { useState } from 'react';
import { Room } from '@/types';
import RoomCard from '@/components/warroom/RoomCard';
import GoalMatrix from '@/components/warroom/GoalMatrix';
import SummaryChips from '@/components/warroom/SummaryChips';
import SearchBar from '@/components/warroom/SearchBar';

interface WarRoomGridProps {
  rooms: Room[];
  summary: {
    pending: number;
    eng: number;
    qa: number;
    passed: number;
    failed: number;
  };
  channelFilter: string | null;
  onSelectRoom: (roomId: string) => void;
}

export default function WarRoomGrid({
  rooms,
  summary,
  channelFilter,
  onSelectRoom,
}: WarRoomGridProps) {
  const [view, setView] = useState<'grid' | 'matrix'>('grid');

  return (
    <section className="panel panel-center">
      <div className="panel-header">
        <div className="header-left">
          <span className="panel-title">⬡ WAR-ROOMS</span>
          <div className="view-toggle">
            <button
              className={`view-btn${view === 'grid' ? ' active' : ''}`}
              onClick={() => setView('grid')}
            >
              grid
            </button>
            <button
              className={`view-btn${view === 'matrix' ? ' active' : ''}`}
              onClick={() => setView('matrix')}
            >
              matrix
            </button>
          </div>
        </div>
        <SummaryChips {...summary} />
      </div>

      <SearchBar onSelectRoom={onSelectRoom} />

      <div className="panel-body">
        {view === 'grid' ? (
          <div className="room-grid">
            {rooms.length === 0 ? (
              <div className="empty-state">
                <div className="empty-hex">⬡</div>
                <p>No war-rooms active.</p>
                <p className="empty-sub">Launch a plan to get started.</p>
              </div>
            ) : (
              rooms.map((room) => (
                <RoomCard
                  key={room.room_id}
                  room={room}
                  selected={channelFilter === room.room_id}
                  onClick={() => onSelectRoom(room.room_id)}
                />
              ))
            )}
          </div>
        ) : (
          <GoalMatrix rooms={rooms} />
        )}
      </div>
    </section>
  );
}
