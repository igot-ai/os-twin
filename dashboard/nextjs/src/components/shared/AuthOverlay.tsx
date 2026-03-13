'use client';

import { useState } from 'react';

interface AuthOverlayProps {
  show: boolean;
  onLogin: (username: string, password: string) => Promise<boolean>;
  error: string;
}

export default function AuthOverlay({ show, onLogin, error }: AuthOverlayProps) {
  const [user, setUser] = useState('');
  const [pass, setPass] = useState('');

  if (!show) return null;

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
        background: 'rgba(0,0,0,0.8)',
        zIndex: 9999,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          background: '#1e1e1e',
          padding: '2rem',
          borderRadius: '8px',
          width: '300px',
          textAlign: 'center',
        }}
      >
        <h2 style={{ color: '#fff', marginBottom: '1rem' }}>OS Twin Login</h2>
        <input
          type="text"
          placeholder="Username"
          value={user}
          onChange={(e) => setUser(e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '10px',
            borderRadius: '4px',
            border: '1px solid #333',
            background: '#2a2a2a',
            color: '#fff',
          }}
        />
        <input
          type="password"
          placeholder="Password"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '15px',
            borderRadius: '4px',
            border: '1px solid #333',
            background: '#2a2a2a',
            color: '#fff',
          }}
        />
        <button
          onClick={() => onLogin(user, pass)}
          style={{
            width: '100%',
            padding: '10px',
            background: '#4CAF50',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Login
        </button>
        {error && (
          <div style={{ color: '#ff5555', marginTop: '10px', fontSize: '12px' }}>
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
