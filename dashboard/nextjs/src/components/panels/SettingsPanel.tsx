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

// Known variable metadata for nice labels and descriptions
const VAR_META: Record<string, { label: string; desc: string; sensitive?: boolean }> = {
  GOOGLE_API_KEY:      { label: 'Google AI',      desc: 'Gemini API key',            sensitive: true },
  OPENAI_API_KEY:      { label: 'OpenAI',         desc: 'GPT-4 / ChatGPT API key',  sensitive: true },
  ANTHROPIC_API_KEY:   { label: 'Anthropic',      desc: 'Claude API key',            sensitive: true },
  DATALOG_API_KEY:     { label: 'Datalog',        desc: 'Catalog analytics key',     sensitive: true },
  DASHBOARD_PORT:      { label: 'Dashboard Port', desc: 'Port the dashboard runs on' },
  DASHBOARD_HOST:      { label: 'Dashboard Host', desc: 'Bind address (e.g. 0.0.0.0)' },
  OSTWIN_LOG_LEVEL:    { label: 'Log Level',      desc: 'INFO, DEBUG, WARNING' },
};

function maskValue(val: string): string {
  if (val.length <= 8) return '••••••••';
  return val.slice(0, 4) + '•'.repeat(Math.min(val.length - 8, 20)) + val.slice(-4);
}

export default function SettingsPanel({ onClose }: { onClose: () => void }) {
  const [entries, setEntries] = useState<EnvEntry[]>([]);
  const [envPath, setEnvPath] = useState('');
  const [status, setStatus] = useState('');
  const [statusColor, setStatusColor] = useState('');
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
    } catch (e) {
      setStatus('Failed to load .env');
      setStatusColor('var(--red)');
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadEnv(); }, [loadEnv]);

  const updateEntry = (idx: number, field: string, value: unknown) => {
    setEntries(prev => {
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
    setEntries(prev => prev.filter((_, i) => i !== idx));
    setDirty(true);
  };

  const addVariable = () => {
    if (!newKey.trim()) return;
    setEntries(prev => [
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
      setStatus('✓ Saved — restart dashboard to apply');
      setStatusColor('var(--green)');
      setDirty(false);
    } catch (e) {
      setStatus('✗ Save failed');
      setStatusColor('var(--red)');
    }
    setSaving(false);
  };

  const variables = entries
    .map((e, i) => ({ ...e, _idx: i }))
    .filter(e => e.type === 'var');

  return (
    <div style={overlayStyle}>
      <div style={panelStyle}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '16px' }}>⚙</span>
            <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '2px', color: 'var(--cyan)' }}>
              SETTINGS
            </span>
          </div>
          <button onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>

        {/* Path indicator */}
        <div style={pathBarStyle}>
          <span style={{ color: 'var(--text-dim)', fontSize: '9px', letterSpacing: '1px', textTransform: 'uppercase' as const }}>
            File
          </span>
          <code style={{ color: 'var(--amber)', fontSize: '10px' }}>{envPath}</code>
        </div>

        {/* Content */}
        <div style={bodyStyle}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-dim)' }}>
              Loading...
            </div>
          ) : (
            <>
              {/* Variables list */}
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '2px' }}>
                {variables.map((entry) => {
                  const meta = VAR_META[entry.key || ''];
                  const isSensitive = meta?.sensitive;
                  const isVisible = showValues[entry.key || ''];

                  return (
                    <div key={entry._idx} style={{
                      ...varRowStyle,
                      opacity: entry.enabled ? 1 : 0.5,
                      borderColor: entry.enabled ? 'var(--border)' : 'transparent',
                    }}>
                      {/* Toggle switch */}
                      <button
                        onClick={() => toggleEntry(entry._idx)}
                        style={{
                          ...toggleStyle,
                          background: entry.enabled ? 'var(--green)' : 'var(--border)',
                          boxShadow: entry.enabled ? '0 0 6px rgba(0, 255, 136, 0.3)' : 'none',
                        }}
                      >
                        <span style={{
                          ...toggleDot,
                          transform: entry.enabled ? 'translateX(14px)' : 'translateX(0)',
                        }} />
                      </button>

                      {/* Key + description */}
                      <div style={{ flex: '0 0 160px', minWidth: 0 }}>
                        <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text)' }}>
                          {meta?.label || entry.key}
                        </div>
                        <div style={{ fontSize: '8px', color: 'var(--text-dim)', marginTop: '1px' }}>
                          {meta?.desc || entry.key}
                        </div>
                      </div>

                      {/* Value input */}
                      <div style={{ flex: 1, display: 'flex', gap: '4px', alignItems: 'center' }}>
                        <input
                          type={isSensitive && !isVisible ? 'password' : 'text'}
                          value={entry.value || ''}
                          onChange={e => updateEntry(entry._idx, 'value', e.target.value)}
                          style={inputStyle}
                          placeholder="value"
                        />
                        {isSensitive && (
                          <button
                            onClick={() => setShowValues(prev => ({ ...prev, [entry.key || '']: !prev[entry.key || ''] }))}
                            style={eyeBtnStyle}
                            title={isVisible ? 'Hide' : 'Show'}
                          >
                            {isVisible ? '🙈' : '👁'}
                          </button>
                        )}
                      </div>

                      {/* Remove */}
                      <button onClick={() => removeEntry(entry._idx)} style={removeBtnStyle} title="Remove">
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* Add new variable */}
              <div style={addRowStyle}>
                <span style={{ fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '1px', textTransform: 'uppercase' as const }}>
                  Add Variable
                </span>
                <div style={{ display: 'flex', gap: '6px', flex: 1 }}>
                  <input
                    type="text"
                    value={newKey}
                    onChange={e => setNewKey(e.target.value)}
                    placeholder="KEY_NAME"
                    style={{ ...inputStyle, flex: '0 0 180px', textTransform: 'uppercase' as const }}
                    onKeyDown={e => e.key === 'Enter' && addVariable()}
                  />
                  <input
                    type="text"
                    value={newValue}
                    onChange={e => setNewValue(e.target.value)}
                    placeholder="value"
                    style={{ ...inputStyle, flex: 1 }}
                    onKeyDown={e => e.key === 'Enter' && addVariable()}
                  />
                  <button onClick={addVariable} style={addBtnStyle} disabled={!newKey.trim()}>
                    + Add
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div style={footerStyle}>
          {status && (
            <span style={{ fontSize: '10px', color: statusColor }}>{status}</span>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            <button onClick={onClose} style={cancelBtnStyle}>Cancel</button>
            <button
              onClick={saveEnv}
              disabled={saving || !dirty}
              style={{
                ...saveBtnStyle,
                opacity: (saving || !dirty) ? 0.5 : 1,
                cursor: (saving || !dirty) ? 'default' : 'pointer',
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Inline Styles (using CSS variables from globals.css) ──────────────

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.7)',
  backdropFilter: 'blur(4px)',
  zIndex: 9000,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  animation: 'fadeIn 0.2s ease-out',
};

const panelStyle: React.CSSProperties = {
  width: '640px',
  maxWidth: '90vw',
  maxHeight: '80vh',
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 0 40px rgba(0, 212, 255, 0.08), 0 24px 48px rgba(0, 0, 0, 0.5)',
  overflow: 'hidden',
};

const headerStyle: React.CSSProperties = {
  padding: '14px 20px',
  borderBottom: '1px solid var(--border)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  background: 'var(--bg-surface)',
};

const closeBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--text-dim)',
  fontSize: '14px',
  cursor: 'pointer',
  padding: '4px 8px',
  borderRadius: '4px',
  transition: 'color 0.15s',
};

const pathBarStyle: React.CSSProperties = {
  padding: '8px 20px',
  borderBottom: '1px solid var(--border)',
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  background: 'var(--bg-card)',
};

const bodyStyle: React.CSSProperties = {
  flex: 1,
  overflowY: 'auto',
  padding: '16px 20px',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
};

const varRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  padding: '10px 12px',
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  transition: 'all 0.15s',
};

const toggleStyle: React.CSSProperties = {
  width: '30px',
  height: '16px',
  borderRadius: '8px',
  border: 'none',
  cursor: 'pointer',
  position: 'relative',
  transition: 'background 0.2s',
  flexShrink: 0,
};

const toggleDot: React.CSSProperties = {
  display: 'block',
  width: '12px',
  height: '12px',
  borderRadius: '50%',
  background: '#fff',
  position: 'absolute',
  top: '2px',
  left: '2px',
  transition: 'transform 0.2s',
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  padding: '6px 10px',
  color: 'var(--text)',
  fontFamily: "var(--font)",
  fontSize: '11px',
  outline: 'none',
  minWidth: 0,
};

const eyeBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: '12px',
  padding: '2px',
  flexShrink: 0,
};

const removeBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--red)',
  cursor: 'pointer',
  fontSize: '10px',
  padding: '4px 6px',
  borderRadius: '3px',
  opacity: 0.6,
  transition: 'opacity 0.15s',
  flexShrink: 0,
};

const addRowStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  padding: '12px',
  border: '1px dashed var(--border)',
  borderRadius: '6px',
  background: 'var(--glass-bg)',
};

const addBtnStyle: React.CSSProperties = {
  background: 'rgba(0, 212, 255, 0.1)',
  border: '1px solid var(--cyan)',
  color: 'var(--cyan)',
  borderRadius: '4px',
  padding: '6px 14px',
  fontFamily: "var(--font)",
  fontSize: '10px',
  fontWeight: 700,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  transition: 'all 0.15s',
};

const footerStyle: React.CSSProperties = {
  padding: '12px 20px',
  borderTop: '1px solid var(--border)',
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  background: 'var(--bg-surface)',
};

const cancelBtnStyle: React.CSSProperties = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border)',
  color: 'var(--text-dim)',
  borderRadius: '4px',
  padding: '6px 16px',
  fontFamily: "var(--font)",
  fontSize: '10px',
  cursor: 'pointer',
  transition: 'all 0.15s',
};

const saveBtnStyle: React.CSSProperties = {
  background: 'rgba(0, 255, 136, 0.1)',
  border: '1px solid var(--green)',
  color: 'var(--green)',
  borderRadius: '4px',
  padding: '6px 20px',
  fontFamily: "var(--font)",
  fontSize: '10px',
  fontWeight: 700,
  cursor: 'pointer',
  transition: 'all 0.15s',
};
