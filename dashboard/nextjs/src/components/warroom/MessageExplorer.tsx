'use client';

import { useState, useEffect, useCallback } from 'react';
import { Message, Room } from '@/types';
import { apiGet } from '@/lib/api';
import { fmtTime } from '@/lib/utils';

interface MessageExplorerProps {
  room: Room;
  planId?: string;
  onClose: () => void;
}

export default function MessageExplorer({ room, planId, onClose }: MessageExplorerProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    from: '',
    type: '',
    q: '',
    limit: 50
  });
  const [analysis, setAnalysis] = useState<any>(null);

  const fetchMessages = useCallback(async () => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams();
      if (filters.from) queryParams.append('from', filters.from);
      if (filters.type) queryParams.append('type', filters.type);
      if (filters.q) queryParams.append('q', filters.q);
      queryParams.append('limit', filters.limit.toString());

      const base = planId
        ? `/api/plans/${planId}/rooms/${room.room_id}/channel`
        : `/api/rooms/${room.room_id}/channel`;
      const data = await apiGet<{ messages: Message[] }>(
        `${base}?${queryParams.toString()}`
      );
      setMessages(data.messages || []);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    } finally {
      setLoading(false);
    }
  }, [room.room_id, planId, filters.from, filters.type, filters.q, filters.limit]);

  const fetchAnalysis = async () => {
    try {
      const queryParams = new URLSearchParams();
      if (filters.from) queryParams.append('from', filters.from);
      if (filters.type) queryParams.append('type', filters.type);
      if (filters.q) queryParams.append('q', filters.q);

      const analyzeBase = planId
        ? `/api/plans/${planId}/rooms/${room.room_id}/analyze`
        : `/api/rooms/${room.room_id}/analyze`;
      const data = await apiGet<any>(
        `${analyzeBase}?${queryParams.toString()}`
      );
      setAnalysis(data);
    } catch (error) {
      console.error('Failed to fetch analysis:', error);
    }
  };

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchMessages();
  };

  return (
    <div className="message-explorer glass" style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: 100,
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg)',
      padding: '16px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', alignItems: 'center' }}>
        <h2 style={{ color: 'var(--cyan)' }}>Message Explorer: {room.room_id}</h2>
        <button onClick={onClose} style={{
          background: 'none',
          border: '1px solid var(--border)',
          color: 'var(--text)',
          padding: '4px 8px',
          cursor: 'pointer'
        }}>Close</button>
      </div>

      <div className="explorer-filters" style={{
        display: 'flex',
        gap: '8px',
        marginBottom: '16px',
        flexWrap: 'wrap'
      }}>
        <select 
          value={filters.from} 
          onChange={(e) => setFilters({...filters, from: e.target.value})}
          style={{ background: 'var(--bg-surface)', color: 'var(--text)', border: '1px solid var(--border)', padding: '4px' }}
        >
          <option value="">From: All</option>
          <option value="manager">Manager</option>
          <option value="engineer">Engineer</option>
          <option value="qa">QA</option>
          <option value="architect">Architect</option>
        </select>

        <select 
          value={filters.type} 
          onChange={(e) => setFilters({...filters, type: e.target.value})}
          style={{ background: 'var(--bg-surface)', color: 'var(--text)', border: '1px solid var(--border)', padding: '4px' }}
        >
          <option value="">Type: All</option>
          <option value="task">Task</option>
          <option value="done">Done</option>
          <option value="review">Review</option>
          <option value="pass">Pass</option>
          <option value="fail">Fail</option>
        </select>

        <form onSubmit={handleSearch} style={{ display: 'flex', flex: 1, gap: '4px' }}>
          <input 
            type="text" 
            placeholder="Search messages..." 
            value={filters.q}
            onChange={(e) => setFilters({...filters, q: e.target.value})}
            style={{ 
              flex: 1, 
              background: 'var(--bg-surface)', 
              color: 'var(--text)', 
              border: '1px solid var(--border)', 
              padding: '4px 8px' 
            }}
          />
          <button type="submit" style={{
            background: 'var(--cyan)',
            color: 'black',
            border: 'none',
            padding: '4px 12px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}>Search</button>
        </form>

        <button onClick={fetchAnalysis} style={{
          background: 'var(--purple)',
          color: 'white',
          border: 'none',
          padding: '4px 12px',
          cursor: 'pointer'
        }}>Analyze</button>
      </div>

      {analysis && (
        <div className="analysis-box" style={{
          background: 'rgba(192, 132, 252, 0.1)',
          border: '1px solid var(--purple)',
          padding: '12px',
          marginBottom: '16px',
          borderRadius: '4px'
        }}>
          <h4 style={{ color: 'var(--purple)', marginBottom: '8px' }}>Analysis Summary</h4>
          <p>{analysis.summary}</p>
          <div style={{ marginTop: '8px', fontSize: '10px', color: 'var(--text-dim)' }}>
            Stats: {Object.entries(analysis.stats?.types || {}).map(([t, count]) => `${t}: ${count}`).join(', ')}
          </div>
        </div>
      )}

      <div className="explorer-results" style={{
        flex: 1,
        overflowY: 'auto',
        border: '1px solid var(--border)',
        background: 'var(--bg-surface)'
      }}>
        {loading ? (
          <div style={{ padding: '20px', textAlign: 'center' }}>Loading messages...</div>
        ) : messages.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center' }}>No messages found.</div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`feed-msg feed-${msg.type}`} style={{
              padding: '8px',
              borderBottom: '1px solid var(--border)',
              fontSize: '11px'
            }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '4px' }}>
                <span className="fm-time" style={{ color: 'var(--text-dim)' }}>{fmtTime(msg.ts)}</span>
                <span className="fm-route" style={{ fontWeight: 'bold' }}>{msg.from || msg.from_} &rarr; {msg.to}</span>
                <span className={`fm-type t-${msg.type}`} style={{
                  padding: '0 4px',
                  borderRadius: '2px',
                  background: 'rgba(255,255,255,0.1)'
                }}>{msg.type}</span>
                {msg.ref && <span className="fm-ref" style={{ color: 'var(--cyan)' }}>[{msg.ref}]</span>}
              </div>
              <div className="fm-body" style={{ whiteSpace: 'pre-wrap', color: 'var(--text)' }}>
                {msg.body}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
