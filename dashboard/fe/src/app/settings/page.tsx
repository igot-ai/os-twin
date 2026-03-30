'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '@/lib/api-client';
import { getApiBaseUrl, getWebSocketUrl } from '@/lib/runtime-config';
import { useUIStore } from '@/lib/stores/uiStore';

type ThemeMode = 'light' | 'dark' | 'system';

interface ApiKeysStatus {
  Claude: boolean;
  GPT: boolean;
  Gemini: boolean;
}

const API_KEY_DISPLAY: Record<string, { label: string; prefix: string }> = {
  Claude: { label: 'Anthropic (Claude)', prefix: 'sk-ant-' },
  GPT: { label: 'OpenAI (GPT)', prefix: 'sk-proj-' },
  Gemini: { label: 'Google (Gemini)', prefix: '' },
};

export default function SettingsPage() {
  const { theme, setTheme } = useUIStore();

  const BASE_URL = getApiBaseUrl();
  const wsUrl = getWebSocketUrl();

  const [connectionStatus, setConnectionStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [themeMode, setThemeMode] = useState<ThemeMode>('light');
  const [apiKeys, setApiKeys] = useState<ApiKeysStatus | null>(null);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);

  const checkConnection = useCallback(async () => {
    setConnectionStatus('checking');
    try {
      await apiGet('/status');
      setConnectionStatus('connected');
    } catch {
      setConnectionStatus('disconnected');
    }
  }, []);

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    const fetchApiKeys = async () => {
      try {
        const data = await apiGet<ApiKeysStatus>('/providers/api-keys');
        setApiKeys(data);
      } catch {
        setApiKeys(null);
      } finally {
        setApiKeysLoading(false);
      }
    };
    fetchApiKeys();
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem('theme-mode') as ThemeMode | null;
    if (saved === 'system') {
      setThemeMode('system');
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      setTheme(mq.matches ? 'dark' : 'light');
    } else {
      setThemeMode(theme);
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (themeMode !== 'system') return;

    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => setTheme(e.matches ? 'dark' : 'light');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [themeMode, setTheme]);

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeMode(mode);
    localStorage.setItem('theme-mode', mode);
    if (mode === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      setTheme(mq.matches ? 'dark' : 'light');
    } else {
      setTheme(mode);
    }
  };

  const themeOptions: { mode: ThemeMode; icon: string; label: string }[] = [
    { mode: 'light', icon: 'light_mode', label: 'Light' },
    { mode: 'dark', icon: 'dark_mode', label: 'Dark' },
    { mode: 'system', icon: 'computer', label: 'System' },
  ];

  const connectionIndicator = () => {
    if (connectionStatus === 'checking') {
      return (
        <div className="flex items-center gap-1 px-2 py-1.5 rounded text-[10px] font-bold" style={{ background: 'rgba(234, 179, 8, 0.08)', color: 'var(--color-warning)' }}>
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--color-warning)' }} />
          Checking...
        </div>
      );
    }
    if (connectionStatus === 'connected') {
      return (
        <div className="flex items-center gap-1 px-2 py-1.5 rounded text-[10px] font-bold" style={{ background: 'rgba(16, 185, 129, 0.08)', color: 'var(--color-success)' }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-success)' }} />
          Connected
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1 px-2 py-1.5 rounded text-[10px] font-bold" style={{ background: 'rgba(239, 68, 68, 0.08)', color: 'var(--color-danger)' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-danger)' }} />
        Disconnected
      </div>
    );
  };

  return (
    <div className="p-6 max-w-[1000px] mx-auto fade-in-up">
      <h1 className="text-xl font-extrabold mb-6" style={{ color: 'var(--color-text-main)' }}>Settings</h1>

      {/* API Configuration */}
      <section className="rounded-xl border p-5 mb-4" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
        <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
          <span className="material-symbols-outlined text-base">api</span>
          API Configuration
        </h2>
        <div className="space-y-3">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'var(--color-text-faint)' }}>Backend URL</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 px-3 py-2 rounded-md text-xs font-mono" style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-main)' }}>
                {BASE_URL}
              </div>
              {connectionIndicator()}
            </div>
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'var(--color-text-faint)' }}>WebSocket URL</label>
            <div className="px-3 py-2 rounded-md text-xs font-mono" style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-main)' }}>
              {wsUrl}
            </div>
          </div>
          <p className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
            Configured via <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> environment variable.
          </p>
        </div>
      </section>

      {/* Theme */}
      <section className="rounded-xl border p-5 mb-4" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
        <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
          <span className="material-symbols-outlined text-base">palette</span>
          Appearance
        </h2>
        <div className="flex gap-3">
          {themeOptions.map((opt) => {
            const isActive = themeMode === opt.mode;
            return (
              <button
                key={opt.mode}
                onClick={() => handleThemeChange(opt.mode)}
                className="flex-1 p-4 rounded-lg flex flex-col items-center gap-2"
                style={{
                  border: isActive ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                  background: isActive ? 'var(--color-primary-muted)' : 'transparent',
                }}
              >
                <span
                  className="material-symbols-outlined text-2xl"
                  style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-faint)' }}
                >
                  {opt.icon}
                </span>
                <span
                  className={`text-xs ${isActive ? 'font-semibold' : 'font-medium'}`}
                  style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-faint)' }}
                >
                  {opt.label}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* API Keys */}
      <section className="rounded-xl border p-5" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
        <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
          <span className="material-symbols-outlined text-base">key</span>
          API Keys
        </h2>
        <div className="space-y-3">
          {apiKeysLoading ? (
            <div className="text-xs py-4 text-center" style={{ color: 'var(--color-text-faint)' }}>Loading API key status...</div>
          ) : apiKeys === null ? (
            <div className="text-xs py-4 text-center" style={{ color: 'var(--color-danger)' }}>Failed to load API key status</div>
          ) : (
            Object.entries(apiKeys).map(([provider, configured]) => {
              const display = API_KEY_DISPLAY[provider];
              return (
                <div key={provider} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--color-background)' }}>
                  <div>
                    <div className="text-xs font-semibold" style={{ color: 'var(--color-text-main)' }}>{display?.label ?? provider}</div>
                    {configured && display?.prefix && (
                      <div className="text-[10px] font-mono" style={{ color: 'var(--color-text-faint)' }}>
                        {display.prefix}{'••••••••'}
                      </div>
                    )}
                  </div>
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{
                      background: configured ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                      color: configured ? 'var(--color-success)' : 'var(--color-danger)',
                    }}
                  >
                    {configured ? '✓ Configured' : '✗ Missing'}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
