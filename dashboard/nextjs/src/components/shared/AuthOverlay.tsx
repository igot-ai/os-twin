'use client';

import { useState } from 'react';

interface AuthOverlayProps {
  show: boolean;
  onLogin: (apiKey: string) => Promise<boolean>;
  error: string;
}

export default function AuthOverlay({ show, onLogin, error }: AuthOverlayProps) {
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);

  if (!show) return null;

  const handleSubmit = async () => {
    setLoading(true);
    await onLogin(apiKey);
    setLoading(false);
  };

  return (
    <div
      id="auth-overlay"
      style={{
        display: 'flex',
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        background: 'rgba(0, 0, 0, 0.85)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
          padding: '2.5rem',
          borderRadius: '16px',
          width: '380px',
          textAlign: 'center',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.4)',
        }}
      >
        {/* Icon */}
        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🔑</div>

        <h2
          style={{
            color: '#fff',
            marginBottom: '0.5rem',
            fontSize: '1.4rem',
            fontWeight: 600,
          }}
        >
          Dashboard Authentication
        </h2>

        <p
          style={{
            color: 'rgba(255, 255, 255, 0.5)',
            fontSize: '0.85rem',
            marginBottom: '1.5rem',
            lineHeight: 1.4,
          }}
        >
          Enter the <code style={{ color: '#ffd700', background: 'rgba(255, 215, 0, 0.1)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>OSTWIN_API_KEY</code> from your <code style={{ color: '#ffd700', background: 'rgba(255, 215, 0, 0.1)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>.env</code> file
        </p>

        <input
          type="password"
          placeholder="ostwin_..."
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          style={{
            width: '100%',
            padding: '12px 16px',
            marginBottom: '1rem',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            background: 'rgba(255, 255, 255, 0.05)',
            color: '#fff',
            fontSize: '0.95rem',
            fontFamily: 'monospace',
            outline: 'none',
            transition: 'border-color 0.2s',
            boxSizing: 'border-box',
          }}
          autoFocus
        />

        <button
          onClick={handleSubmit}
          disabled={loading || !apiKey.trim()}
          style={{
            width: '100%',
            padding: '12px',
            background: loading ? '#555' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: loading ? 'wait' : 'pointer',
            fontSize: '0.95rem',
            fontWeight: 600,
            opacity: !apiKey.trim() ? 0.5 : 1,
            transition: 'opacity 0.2s, transform 0.1s',
          }}
        >
          {loading ? 'Verifying...' : 'Authenticate'}
        </button>

        {error && (
          <div
            style={{
              color: '#ff6b6b',
              marginTop: '1rem',
              fontSize: '0.8rem',
              padding: '8px 12px',
              background: 'rgba(255, 107, 107, 0.1)',
              borderRadius: '6px',
              border: '1px solid rgba(255, 107, 107, 0.2)',
            }}
          >
            {error}
          </div>
        )}

        <p
          style={{
            color: 'rgba(255, 255, 255, 0.3)',
            fontSize: '0.75rem',
            marginTop: '1.5rem',
            lineHeight: 1.4,
          }}
        >
          Find your key in <code style={{ color: 'rgba(255, 255, 255, 0.5)' }}>~/.ostwin/.env</code>
        </p>
      </div>
    </div>
  );
}
