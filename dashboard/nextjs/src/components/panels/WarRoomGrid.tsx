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
  onShowDetails?: (roomId: string) => void;
  style?: React.CSSProperties;
}

export default function WarRoomGrid({
  rooms,
  summary,
  channelFilter,
  onSelectRoom,
  onShowDetails,
  style,
}: WarRoomGridProps) {
  const [view, setView] = useState<'grid' | 'matrix' | 'tasks'>('grid');

  return (
    <section className="panel panel-center" style={style}>
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
            <button
              className={`view-btn${view === 'tasks' ? ' active' : ''}`}
              onClick={() => setView('tasks')}
            >
              tasks
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
                  onShowDetails={() => onShowDetails?.(room.room_id)}
                />
              ))
            )}
          </div>
        ) : view === 'matrix' ? (
          <GoalMatrix rooms={rooms} />
        ) : (
          <div className="aggregated-tasks" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
            {rooms.filter(r => r.task_description).length === 0 ? (
               <div className="empty-state"><p>No tasks available.</p></div>
            ) : (
               rooms.filter(r => r.task_description).map(room => (
                 <div key={room.room_id} className="task-agg-item" style={{ background: 'var(--bg-card)', padding: '12px', border: '1px solid var(--border)', borderRadius: '6px' }}>
                   <div style={{ color: 'var(--cyan)', fontWeight: 'bold', marginBottom: '8px' }}>
                     {room.task_ref || room.room_id} — {room.status}
                   </div>
                   <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font)', fontSize: '11px', color: 'var(--text-dim)' }}>
                     {room.task_description}
                   </pre>
                 </div>
               ))
            )}
          </div>
        )}
      </div>
    </section>
  );
}
