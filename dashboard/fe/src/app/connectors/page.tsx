'use client';

import { useState } from 'react';
import { useConnectors } from '@/hooks/use-connectors';
import { ConnectorCard } from '@/components/connectors/ConnectorCard';
import { ConnectorConfigModal } from '@/components/connectors/ConnectorConfigModal';
import { NotificationSettings } from '@/components/connectors/NotificationSettings';
import { useNotificationStore } from '@/lib/stores/notificationStore';

const PLATFORMS = ['telegram', 'discord', 'slack'];

export default function ConnectorsPage() {
  const { config, isLoading, updateConfig, updateSettings, testConnector } = useConnectors();
  const addToast = useNotificationStore((s) => s.addToast);
  const [configPlatform, setConfigPlatform] = useState<string | null>(null);
  const [testingPlatform, setTestingPlatform] = useState<string | null>(null);

  const enabledPlatforms = config?.settings?.enabled_platforms ?? [];
  const importantEvents = config?.settings?.important_events ?? [];

  const handleToggle = async (platform: string, enabled: boolean) => {
    const next = enabled
      ? [...enabledPlatforms, platform]
      : enabledPlatforms.filter((p) => p !== platform);
    try {
      await updateSettings({ important_events: importantEvents, enabled_platforms: next });
    } catch {
      addToast({ type: 'error', title: 'Error', message: 'Failed to update platform status.' });
    }
  };

  const handleTest = async (platform: string) => {
    setTestingPlatform(platform);
    try {
      await testConnector(platform);
      addToast({ type: 'success', title: 'Test Sent', message: `Test message sent via ${platform}.` });
    } catch {
      addToast({ type: 'error', title: 'Test Failed', message: `Could not send test message via ${platform}.` });
    } finally {
      setTestingPlatform(null);
    }
  };

  const handleEventsChange = async (events: string[]) => {
    try {
      await updateSettings({ important_events: events, enabled_platforms: enabledPlatforms });
    } catch {
      addToast({ type: 'error', title: 'Error', message: 'Failed to update notification settings.' });
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto fade-in-up">
        <div className="h-8 w-48 rounded-md animate-pulse mb-6" style={{ background: 'var(--color-border)' }} />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border p-5 h-40 animate-pulse"
              style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1200px] mx-auto fade-in-up space-y-6">
      <div>
        <h1 className="text-xl font-extrabold" style={{ color: 'var(--color-text-main)' }}>
          Connectors
        </h1>
        <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
          Configure chat platform integrations to receive notifications and interact with your agents.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PLATFORMS.map((platform) => (
          <ConnectorCard
            key={platform}
            platform={platform}
            adapter={config?.adapters?.[platform]}
            enabled={enabledPlatforms.includes(platform)}
            onToggle={(enabled) => handleToggle(platform, enabled)}
            onConfigure={() => setConfigPlatform(platform)}
            onTest={() => handleTest(platform)}
            testing={testingPlatform === platform}
          />
        ))}
      </div>

      <NotificationSettings
        selectedEvents={importantEvents}
        onChange={handleEventsChange}
      />

      <ConnectorConfigModal
        platform={configPlatform}
        adapter={configPlatform ? config?.adapters?.[configPlatform] : undefined}
        onClose={() => setConfigPlatform(null)}
        onSave={updateConfig}
        onTest={testConnector}
      />
    </div>
  );
}
