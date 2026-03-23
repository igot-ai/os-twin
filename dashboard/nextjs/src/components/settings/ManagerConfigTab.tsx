'use client';

import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

interface ManagerConfigData {
  model?: string;
  poll_interval_seconds?: number;
  max_concurrent_rooms?: number;
  max_engineer_retries?: number;
  state_timeout_seconds?: number;
  auto_approve_tools?: boolean;
  auto_expand_plan?: boolean;
  smart_assignment?: boolean;
  dynamic_pipelines?: boolean;
  capability_matching?: boolean;
  preflight_skill_check?: boolean;
  [key: string]: unknown;
}

const GENERAL_FIELDS: { key: keyof ManagerConfigData; label: string }[] = [
  { key: 'model', label: 'Model' },
  { key: 'poll_interval_seconds', label: 'Poll Interval' },
  { key: 'max_concurrent_rooms', label: 'Max Concurrent Rooms' },
  { key: 'max_engineer_retries', label: 'Max Engineer Retries' },
  { key: 'state_timeout_seconds', label: 'State Timeout' },
];

const FLAG_FIELDS: { key: keyof ManagerConfigData; label: string }[] = [
  { key: 'auto_approve_tools', label: 'Auto Approve Tools' },
  { key: 'auto_expand_plan', label: 'Auto Expand Plan' },
  { key: 'smart_assignment', label: 'Smart Assignment' },
  { key: 'dynamic_pipelines', label: 'Dynamic Pipelines' },
  { key: 'capability_matching', label: 'Capability Matching' },
  { key: 'preflight_skill_check', label: 'Preflight Skill Check' },
];

function formatValue(val: unknown): string {
  if (val === undefined || val === null) return '\u2014';
  if (typeof val === 'number') return `${val}`;
  return String(val);
}

export default function ManagerConfigTab() {
  const [config, setConfig] = useState<ManagerConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiGet<{ manager?: ManagerConfigData }>('/api/config')
      .then((data) => {
        setConfig(data.manager || {});
      })
      .catch(() => {
        setError('Failed to load configuration');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading configuration...</p>
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

  if (!config) return null;

  return (
    <div className="config-tab">
      <h3 className="section-title">General</h3>
      <div className="settings-config-grid">
        {GENERAL_FIELDS.map((f) => (
          <div key={f.key} className="config-field">
            <span className="config-label">{f.label}</span>
            <code className="config-value">{formatValue(config[f.key])}</code>
          </div>
        ))}
      </div>

      <h3 className="section-title">Feature Flags</h3>
      <div className="settings-config-grid">
        {FLAG_FIELDS.map((f) => {
          const val = config[f.key];
          const isOn = val === true;
          const isOff = val === false;

          return (
            <div key={f.key} className="config-field">
              <span className="config-label">{f.label}</span>
              {isOn || isOff ? (
                <span className={`settings-flag-badge ${isOn ? 'on' : 'off'}`}>
                  {isOn ? 'ON' : 'OFF'}
                </span>
              ) : (
                <span className="config-value">{formatValue(val)}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
