'use client';

import { useState } from 'react';
import EnvVarsTab from '@/components/settings/EnvVarsTab';
import ManagerConfigTab from '@/components/settings/ManagerConfigTab';
import SystemStatusTab from '@/components/settings/SystemStatusTab';

type Tab = 'env' | 'config' | 'status';

const tabs: { key: Tab; label: string }[] = [
  { key: 'env', label: 'Environment Variables' },
  { key: 'config', label: 'Manager Config' },
  { key: 'status', label: 'System Status' },
];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('env');

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div className="settings-body">
        <div className="tab-bar">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {tab === 'env' && <EnvVarsTab />}
          {tab === 'config' && <ManagerConfigTab />}
          {tab === 'status' && <SystemStatusTab />}
        </div>
      </div>
    </div>
  );
}
