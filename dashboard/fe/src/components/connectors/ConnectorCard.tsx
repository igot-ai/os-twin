'use client';

import { Button } from '@/components/ui/Button';

const PLATFORM_META: Record<string, { icon: string; label: string }> = {
  telegram: { icon: 'send', label: 'Telegram' },
  discord: { icon: 'tag', label: 'Discord' },
  slack: { icon: 'chat', label: 'Slack' },
};

function isConfigured(platform: string, adapter: Record<string, string> | undefined): boolean {
  if (!adapter) return false;
  const v = (k: string) => (adapter[k] ?? '').trim() !== '';
  switch (platform) {
    case 'telegram':
      return v('bot_token') && v('chat_id');
    case 'discord':
      return v('webhook_url');
    case 'slack':
      return v('webhook_url') || (v('bot_token') && v('channel_id'));
    default:
      return false;
  }
}

interface ConnectorCardProps {
  platform: string;
  adapter?: Record<string, string>;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  onConfigure: () => void;
  onTest: () => void;
  testing?: boolean;
}

export function ConnectorCard({
  platform,
  adapter,
  enabled,
  onToggle,
  onConfigure,
  onTest,
  testing,
}: ConnectorCardProps) {
  const meta = PLATFORM_META[platform] ?? { icon: 'hub', label: platform };
  const configured = isConfigured(platform, adapter);

  return (
    <div
      className="rounded-xl border p-5 flex flex-col gap-4"
      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--color-primary-muted)' }}
          >
            <span
              className="material-symbols-outlined text-xl"
              style={{ color: 'var(--color-primary)' }}
            >
              {meta.icon}
            </span>
          </div>
          <div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--color-text-main)' }}>
              {meta.label}
            </h3>
            <StatusBadge configured={configured} enabled={enabled} />
          </div>
        </div>

        {configured && (
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only peer"
            />
            <div
              className="w-9 h-5 rounded-full peer-focus:ring-2 peer-focus:ring-primary/20 transition-colors after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"
              style={{
                background: enabled ? 'var(--color-primary)' : 'var(--color-border)',
              }}
            />
          </label>
        )}
      </div>

      <div className="flex items-center gap-2 mt-auto">
        <Button variant="outline" size="sm" onClick={onConfigure}>
          <span className="material-symbols-outlined text-sm mr-1.5">settings</span>
          Configure
        </Button>
        {configured && enabled && (
          <Button variant="ghost" size="sm" onClick={onTest} isLoading={testing}>
            <span className="material-symbols-outlined text-sm mr-1.5">play_arrow</span>
            Test
          </Button>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ configured, enabled }: { configured: boolean; enabled: boolean }) {
  if (!configured) {
    return (
      <span
        className="text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-1"
        style={{ background: 'var(--color-background)', color: 'var(--color-text-faint)' }}
      >
        Not Configured
      </span>
    );
  }

  if (!enabled) {
    return (
      <span
        className="text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-1"
        style={{ background: 'var(--color-background)', color: 'var(--color-text-muted)' }}
      >
        Disabled
      </span>
    );
  }

  return (
    <span
      className="text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-1"
      style={{ background: 'rgba(16, 185, 129, 0.08)', color: 'var(--color-success)' }}
    >
      Connected
    </span>
  );
}
