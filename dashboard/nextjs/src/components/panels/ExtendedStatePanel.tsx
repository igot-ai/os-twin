'use client';

import React, { useEffect, useState } from 'react';
import { Room } from '@/types';
import { apiGet } from '@/lib/api';

interface ExtendedStatePanelProps {
  roomId: string;
  onClose: () => void;
}

export default function ExtendedStatePanel({ roomId, onClose }: ExtendedStatePanelProps) {
  const [room, setRoom] = useState<Room | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRoomState() {
      setLoading(true);
      try {
        const data = await apiGet<Room>(`/api/rooms/${roomId}/state`);
        setRoom(data);
      } catch (err) {
        console.error('Failed to fetch room state:', err);
        setError('Failed to load room state');
      } finally {
        setLoading(false);
      }
    }

    if (roomId) {
      fetchRoomState();
    }
  }, [roomId]);

  if (loading) {
    return (
      <div className="extended-state-panel glass">
        <div className="panel-loading">Scanning room state...</div>
      </div>
    );
  }

  if (error || !room) {
    return (
      <div className="extended-state-panel glass">
        <div className="panel-error">{error || 'Room not found'}</div>
        <button onClick={onClose}>Close</button>
      </div>
    );
  }

  return (
    <div className="extended-state-panel glass shadow-lg">
      <div className="panel-header border-b border-white/10 pb-2 mb-4 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-cyan-400 uppercase tracking-widest">{room.room_id}</h2>
          <div className="text-xs text-dim">{room.task_ref}</div>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="panel-content overflow-y-auto pr-2 max-h-[80vh]">
        {/* Status Section */}
        <section className="mb-6">
          <h3 className="text-xs font-semibold uppercase text-dim mb-2 tracking-wider">Status & Lifecycle</h3>
          <div className="flex gap-4 items-center mb-3">
             <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getStatusColor(room.status)}`}>
               {room.status}
             </span>
             <span className="text-xs text-dim">Retries: {room.retries}</span>
             <span className="text-xs text-dim">Msgs: {room.message_count}</span>
          </div>
          
          {room.lifecycle && room.lifecycle.states && (
            <div className="lifecycle-viz bg-black/20 p-3 rounded border border-white/5">
              <div className="text-[10px] text-dim mb-2 uppercase">State Machine</div>
              <div className="flex flex-col gap-3">
                {Object.entries(room.lifecycle.states).map(([stateName, state]) => (
                  <div key={stateName} className="flex items-start gap-2">
                    <div 
                      className={`px-2 py-1 rounded text-[10px] border flex-shrink-0 w-24 text-center ${stateName === room.status ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400 font-bold' : 'border-white/10 text-dim'}`}
                    >
                      {stateName}
                    </div>
                    <div className="flex flex-col gap-1 mt-1">
                      {state.transitions && Object.entries(state.transitions).map(([trigger, target]) => (
                        <div key={trigger} className="text-[9px] text-dim flex items-center gap-1">
                          <span className="text-white/40">─{trigger}→</span>
                          <span className={target === room.status ? 'text-cyan-400 font-bold' : ''}>{target}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Roles Section */}
        {room.roles && room.roles.length > 0 && (
          <section className="mb-6">
            <h3 className="text-xs font-semibold uppercase text-dim mb-2 tracking-wider">Role Instances</h3>
            <div className="grid grid-cols-1 gap-2">
              {room.roles.map((role, idx) => (
                <div key={idx} className="bg-white/5 p-2 rounded border border-white/5 flex justify-between items-center">
                  <div>
                    <div className="text-xs font-bold text-white">{role.role} <span className="text-[10px] text-dim">#{role.instance_id}</span></div>
                    <div className="text-[10px] text-dim">{String(role.model || 'unknown')}</div>
                  </div>
                  <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded ${role.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-white/10 text-dim'}`}>
                    {String(role.status || 'idle')}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Artifacts Section */}
        {room.artifact_files && room.artifact_files.length > 0 && (
          <section className="mb-6">
            <h3 className="text-xs font-semibold uppercase text-dim mb-2 tracking-wider">Artifacts</h3>
            <div className="flex flex-wrap gap-1.5">
              {room.artifact_files.map((file, idx) => (
                <div key={idx} className="text-[10px] bg-white/5 px-2 py-1 rounded border border-white/5 text-dim hover:text-cyan-300 hover:border-cyan-500/30 cursor-pointer transition-colors">
                  {file}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Audit Tail */}
        {room.audit_tail && room.audit_tail.length > 0 && (
          <section className="mb-6">
            <h3 className="text-xs font-semibold uppercase text-dim mb-2 tracking-wider">Audit Log (Tail)</h3>
            <div className="bg-black/40 p-2 rounded border border-white/5 font-mono text-[10px] overflow-x-auto">
              {room.audit_tail.map((line, idx) => (
                <div key={idx} className="whitespace-nowrap border-b border-white/5 last:border-0 py-0.5 opacity-80 hover:opacity-100">
                  {line}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Config Section */}
        {room.config && Object.keys(room.config).length > 0 && (
          <section className="mb-6">
            <h3 className="text-xs font-semibold uppercase text-dim mb-2 tracking-wider">Room Config</h3>
            <pre className="text-[10px] bg-black/20 p-2 rounded border border-white/5 text-dim overflow-x-auto">
              {JSON.stringify(room.config, null, 2)}
            </pre>
          </section>
        )}
      </div>

      <style jsx>{`
        .extended-state-panel {
          position: fixed;
          top: 60px;
          right: 20px;
          width: 380px;
          max-height: calc(100vh - 80px);
          z-index: 1001;
          padding: 16px;
          display: flex;
          flex-direction: column;
          border-radius: 8px;
        }
        .panel-loading, .panel-error {
          padding: 40px;
          text-align: center;
          color: var(--text-dim);
        }
        .text-dim { color: var(--text-dim); }
      `}</style>
    </div>
  );
}

function getStatusColor(status: string) {
  switch (status) {
    case 'passed': return 'bg-green-500/20 text-green-400';
    case 'failed-final': return 'bg-red-500/20 text-red-400';
    case 'engineering': return 'bg-cyan-500/20 text-cyan-400';
    case 'qa-review': return 'bg-purple-500/20 text-purple-400';
    case 'fixing': return 'bg-orange-500/20 text-orange-400';
    case 'paused': return 'bg-white/10 text-dim';
    default: return 'bg-white/10 text-dim';
  }
}
