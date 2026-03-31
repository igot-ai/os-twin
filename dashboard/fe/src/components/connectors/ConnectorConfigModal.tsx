'use client';

import { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { useNotificationStore } from '@/lib/stores/notificationStore';

interface FieldDef {
  key: string;
  label: string;
  required?: boolean;
  secret?: boolean;
  placeholder?: string;
}

const PLATFORM_FIELDS: Record<string, FieldDef[]> = {
  telegram: [
    { key: 'bot_token', label: 'Bot Token', required: true, secret: true, placeholder: '123456:ABC-DEF...' },
    { key: 'chat_id', label: 'Chat ID', required: true, placeholder: '-1001234567890' },
    { key: 'bot_username', label: 'Bot Username', placeholder: '@my_bot' },
    { key: 'secret_token', label: 'Secret Token', secret: true, placeholder: 'Webhook verification secret' },
  ],
  discord: [
    { key: 'webhook_url', label: 'Webhook URL', required: true, placeholder: 'https://discord.com/api/webhooks/...' },
    { key: 'public_key', label: 'Public Key', secret: true, placeholder: 'Interaction verification key' },
  ],
  slack: [
    { key: 'bot_token', label: 'Bot Token', secret: true, placeholder: 'xoxb-...' },
    { key: 'channel_id', label: 'Channel ID', placeholder: 'C01234ABCDE' },
    { key: 'signing_secret', label: 'Signing Secret', secret: true, placeholder: 'Request signature secret' },
    { key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://hooks.slack.com/services/...' },
  ],
};

const PLATFORM_LABELS: Record<string, string> = {
  telegram: 'Telegram',
  discord: 'Discord',
  slack: 'Slack',
};

function isValid(platform: string, values: Record<string, string>): boolean {
  const v = (k: string) => (values[k] ?? '').trim() !== '';
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

interface ConnectorConfigModalProps {
  platform: string | null;
  adapter?: Record<string, string>;
  onClose: () => void;
  onSave: (platform: string, config: Record<string, string>) => Promise<void>;
  onTest: (platform: string) => Promise<unknown>;
}

export function ConnectorConfigModal({
  platform,
  adapter,
  onClose,
  onSave,
  onTest,
}: ConnectorConfigModalProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [visibleFields, setVisibleFields] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const addToast = useNotificationStore((s) => s.addToast);

  useEffect(() => {
    if (platform) {
      setValues(adapter ? { ...adapter } : {});
      setVisibleFields(new Set());
    }
  }, [platform, adapter]);

  if (!platform) return null;

  const fields = PLATFORM_FIELDS[platform] ?? [];
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
  const resolvedBase = typeof window !== 'undefined' && !apiBase.startsWith('http')
    ? `${window.location.origin}${apiBase}`
    : apiBase;
  const webhookUrl = `${resolvedBase}/chat-adapters/${platform}/webhook`;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(platform, values);
      addToast({ type: 'success', title: 'Saved', message: `${PLATFORM_LABELS[platform]} configuration saved.` });
      onClose();
    } catch {
      addToast({ type: 'error', title: 'Error', message: 'Failed to save configuration.' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      await onSave(platform, values);
      await onTest(platform);
      addToast({ type: 'success', title: 'Test Sent', message: `Test message sent via ${PLATFORM_LABELS[platform]}.` });
    } catch {
      addToast({ type: 'error', title: 'Test Failed', message: `Could not send test message via ${PLATFORM_LABELS[platform]}.` });
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    setSaving(true);
    try {
      await onSave(platform, {});
      addToast({ type: 'success', title: 'Disconnected', message: `${PLATFORM_LABELS[platform]} configuration removed.` });
      onClose();
    } catch {
      addToast({ type: 'error', title: 'Error', message: 'Failed to remove configuration.' });
    } finally {
      setSaving(false);
    }
  };

  const toggleVisibility = (key: string) => {
    setVisibleFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const hasExistingConfig = adapter && Object.values(adapter).some((v) => v && v.trim() !== '');

  return (
    <Modal
      isOpen={!!platform}
      onClose={onClose}
      title={`Configure ${PLATFORM_LABELS[platform] ?? platform}`}
      size="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <div>
            {hasExistingConfig && (
              <Button variant="danger" size="sm" onClick={handleDisconnect} isLoading={saving}>
                Disconnect
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isValid(platform, values) && (
              <Button variant="ghost" size="sm" onClick={handleTest} isLoading={testing}>
                <span className="material-symbols-outlined text-sm mr-1.5">play_arrow</span>
                Test
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              isLoading={saving}
              disabled={!isValid(platform, values)}
            >
              Save
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {fields.map((field) => (
          <div key={field.key}>
            <label
              className="text-[11px] font-semibold uppercase tracking-wider mb-1.5 flex items-center gap-1"
              style={{ color: 'var(--color-text-faint)' }}
            >
              {field.label}
              {field.required && <span style={{ color: 'var(--color-danger)' }}>*</span>}
            </label>
            <div className="relative">
              <input
                type={field.secret && !visibleFields.has(field.key) ? 'password' : 'text'}
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={field.placeholder}
                className="w-full px-3 py-2 rounded-md text-xs font-mono pr-9"
                style={{
                  background: 'var(--color-background)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-main)',
                }}
              />
              {field.secret && (
                <button
                  type="button"
                  onClick={() => toggleVisibility(field.key)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded"
                  style={{ color: 'var(--color-text-faint)' }}
                >
                  <span className="material-symbols-outlined text-sm">
                    {visibleFields.has(field.key) ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              )}
            </div>
          </div>
        ))}

        <div>
          <label
            className="text-[11px] font-semibold uppercase tracking-wider mb-1.5 block"
            style={{ color: 'var(--color-text-faint)' }}
          >
            Webhook URL
          </label>
          <div className="flex items-center gap-2">
            <div
              className="flex-1 px-3 py-2 rounded-md text-xs font-mono truncate"
              style={{
                background: 'var(--color-background)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-muted)',
              }}
            >
              {webhookUrl}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => {
                navigator.clipboard.writeText(webhookUrl);
                addToast({ type: 'info', title: 'Copied', message: 'Webhook URL copied to clipboard.' });
              }}
            >
              <span className="material-symbols-outlined text-sm">content_copy</span>
            </Button>
          </div>
          <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
            Use this URL to configure incoming webhooks on the platform side.
          </p>
        </div>
      </div>
    </Modal>
  );
}
