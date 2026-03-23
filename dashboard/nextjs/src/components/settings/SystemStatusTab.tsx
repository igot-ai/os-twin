'use client';

import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';
import { useApp } from '@/contexts/AppContext';

interface StatusData {
  running: boolean;
  pid?: number;
}

export default function SystemStatusTab() {
  const { connected } = useApp();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<StatusData>('/api/status')
      .then((data) => setStatus(data))
      .catch(() => setError('Failed to load status'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading status...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="config-tab">
      <h3 className="section-title">Manager Process</h3>
      <div className="settings-config-grid">
        <div className="config-field">
          <span className="config-label">Status</span>
          <span className={`settings-flag-badge ${status?.running ? 'on' : 'off'}`}>
            {status?.running ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
        {status?.pid && (
          <div className="config-field">
            <span className="config-label">PID</span>
            <code className="config-value">{status.pid}</code>
          </div>
        )}
      </div>

      <h3 className="section-title">Connections</h3>
      <div className="settings-config-grid">
        <div className="config-field">
          <span className="config-label">WebSocket</span>
          <span className={`settings-flag-badge ${connected ? 'on' : 'off'}`}>
            {connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      <h3 className="section-title">Dashboard</h3>
      <div className="settings-config-grid">
        <div className="config-field">
          <span className="config-label">Version</span>
          <code className="config-value">v0.1.0</code>
        </div>
      </div>
    </div>
  );
}
