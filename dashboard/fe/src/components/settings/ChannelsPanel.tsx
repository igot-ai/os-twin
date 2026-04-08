'use client';

import { ProvenanceChip } from './ProvenanceChip';
import type { ChannelsNamespace, ChannelPlatformSettings } from '@/types/settings';

export interface ChannelsPanelProps {
  channels: ChannelsNamespace;
  provenance?: Record<string, string>;
  onUpdate: (platform: string, value: Partial<ChannelPlatformSettings>) => void;
  onVaultClick: (platform: string) => void;
  vaultStatus: Record<string, boolean>;
}

const PLATFORM_ICONS: Record<string, string> = {
  telegram: 'telegram',
  slack: 'slack',
  discord: 'discord',
};

export function ChannelsPanel({
  channels,
  provenance = {},
  onUpdate,
  onVaultClick,
  vaultStatus,
}: ChannelsPanelProps) {
  const platforms = Object.entries(channels);

  if (platforms.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        <span className="material-symbols-outlined text-4xl mb-2 block">hub</span>
        <p className="text-xs">No channels configured</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {platforms.map(([platformName, platformSettings]) => {
        const vaultSet = vaultStatus[platformName] || false;

        return (
          <div
            key={platformName}
            className="rounded-lg border p-4"
            style={{
              background: '#ffffff',
              borderColor: '#e2e8f0',
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span
                  className="material-symbols-outlined text-lg"
                  style={{ color: '#0f172a' }}
                >
                  {PLATFORM_ICONS[platformName] || 'hub'}
                </span>
                <span className="text-sm font-bold uppercase" style={{ color: '#0f172a' }}>
                  {platformName}
                </span>
              </div>
              <button
                onClick={() => onVaultClick(platformName)}
                className="text-lg hover:opacity-80 transition-opacity"
                title={vaultSet ? 'Vault key set' : 'Vault key not set'}
              >
                {vaultSet ? '🔑' : '🗝️'}
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold uppercase tracking-wider mb-1 block text-slate-500">
                  Status
                </label>
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={platformSettings?.enabled || false}
                      onChange={(e) => onUpdate(platformName, { enabled: e.target.checked })}
                      className="sr-only"
                    />
                    <div
                      className="relative w-10 h-5 rounded-full transition-colors"
                      style={{
                        background: platformSettings?.enabled ? '#2563eb' : '#94a3b8',
                      }}
                    >
                      <div
                        className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform"
                        style={{
                          left: platformSettings?.enabled ? '22px' : '2px',
                        }}
                      />
                    </div>
                  </label>
                  <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>
                    {platformSettings?.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>

              {provenance[platformName] && (
                <ProvenanceChip source={provenance[platformName]} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
