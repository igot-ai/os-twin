'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';

interface EnvEntry {
  type: 'var' | 'comment' | 'blank';
  key?: string;
  value?: string;
  enabled?: boolean;
  text?: string;
}

interface EnvData {
  path: string;
  entries: EnvEntry[];
  raw: string;
}

const VAR_META: Record<string, { label: string; desc: string; sensitive?: boolean }> = {
  GOOGLE_API_KEY: { label: 'Google AI', desc: 'Gemini API key', sensitive: true },
  OPENAI_API_KEY: { label: 'OpenAI', desc: 'GPT-4 / ChatGPT API key', sensitive: true },
  ANTHROPIC_API_KEY: { label: 'Anthropic', desc: 'Claude API key', sensitive: true },
  DATALOG_API_KEY: { label: 'Datalog', desc: 'Catalog analytics key', sensitive: true },
  OSTWIN_API_KEY: { label: 'OS Twin API Key', desc: 'Internal dashboard auth key', sensitive: true },
  OSTWIN_PROJECT_DIR: { label: 'Project Directory', desc: 'Override project root directory' },
  DASHBOARD_PORT: { label: 'Dashboard Port', desc: 'Port the dashboard runs on' },
  DASHBOARD_HOST: { label: 'Dashboard Host', desc: 'Bind address (e.g. 0.0.0.0)' },
  OSTWIN_LOG_LEVEL: { label: 'Log Level', desc: 'INFO, DEBUG, WARNING' },
};

export default function EnvVarsTab() {
  const [entries, setEntries] = useState<EnvEntry[]>([]);
  const [envPath, setEnvPath] = useState('');
  const [status, setStatus] = useState('');
  const [statusType, setStatusType] = useState<'success' | 'error' | ''>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [dirty, setDirty] = useState(false);

  const loadEnv = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiGet<EnvData>('/api/env');
      setEntries(data.entries);
      setEnvPath(data.path);
    } catch {
      setStatus('Failed to load .env');
      setStatusType('error');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadEnv();
  }, [loadEnv]);

  const updateEntry = (idx: number, field: string, value: unknown) => {
    setEntries((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
    setDirty(true);
  };

  const toggleEntry = (idx: number) => {
    updateEntry(idx, 'enabled', !entries[idx].enabled);
  };

  const removeEntry = (idx: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== idx));
    setDirty(true);
  };

  const addVariable = () => {
    if (!newKey.trim()) return;
    setEntries((prev) => [
      ...prev,
      { type: 'var', key: newKey.trim().toUpperCase(), value: newValue, enabled: true },
    ]);
    setNewKey('');
    setNewValue('');
    setDirty(true);
  };

  const saveEnv = async () => {
    setSaving(true);
    setStatus('');
    try {
      await apiPost('/api/env', { entries });
      setStatus('Saved — restart dashboard to apply');
      setStatusType('success');
      setDirty(false);
    } catch {
      setStatus('Save failed');
      setStatusType('error');
    }
    setSaving(false);
  };

  const variables = entries.map((e, i) => ({ ...e, _idx: i })).filter((e) => e.type === 'var');

  if (loading) {
    return (
      <div className="empty-state">
        <p>Loading environment variables...</p>
      </div>
    );
  }

  return (
    <div className="env-vars-tab">
      <div className="env-path-bar">
        <span className="env-path-label">File</span>
        <code className="env-path-value">{envPath}</code>
      </div>

      <div className="env-var-list">
        {variables.map((entry) => {
          const meta = VAR_META[entry.key || ''];
          const isSensitive = meta?.sensitive;
          const isVisible = showValues[entry.key || ''];

          return (
            <div
              key={entry._idx}
              className={`env-var-row${entry.enabled ? '' : ' disabled'}`}
            >
              <button
                className={`env-toggle${entry.enabled ? ' on' : ''}`}
                onClick={() => toggleEntry(entry._idx)}
              >
                <span className="env-toggle-dot" />
              </button>

              <div className="env-var-info">
                <span className="env-var-name">{meta?.label || entry.key}</span>
                <span className="env-var-desc">{meta?.desc || entry.key}</span>
              </div>

              <div className="env-var-input-group">
                <input
                  type={isSensitive && !isVisible ? 'password' : 'text'}
                  value={entry.value || ''}
                  onChange={(e) => updateEntry(entry._idx, 'value', e.target.value)}
                  className="env-var-input"
                  placeholder="value"
                />
                {isSensitive && (
                  <button
                    className="env-eye-btn"
                    onClick={() =>
                      setShowValues((prev) => ({
                        ...prev,
                        [entry.key || '']: !prev[entry.key || ''],
                      }))
                    }
                    title={isVisible ? 'Hide' : 'Show'}
                  >
                    {isVisible ? '🙈' : '👁'}
                  </button>
                )}
              </div>

              <button
                className="env-remove-btn"
                onClick={() => removeEntry(entry._idx)}
                title="Remove"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>

      <div className="env-add-row">
        <span className="env-add-label">Add Variable</span>
        <div className="env-add-fields">
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="KEY_NAME"
            className="env-var-input env-key-input"
            onKeyDown={(e) => e.key === 'Enter' && addVariable()}
          />
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="value"
            className="env-var-input"
            onKeyDown={(e) => e.key === 'Enter' && addVariable()}
          />
          <button
            className="env-add-btn"
            onClick={addVariable}
            disabled={!newKey.trim()}
          >
            + Add
          </button>
        </div>
      </div>

      <div className="env-footer">
        {status && (
          <span className={`env-status ${statusType}`}>{status}</span>
        )}
        <button
          className="env-save-btn"
          onClick={saveEnv}
          disabled={saving || !dirty}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
}
