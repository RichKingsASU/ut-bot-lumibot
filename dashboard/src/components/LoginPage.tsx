import React, { useState } from 'react';
import { supabase } from '../lib/supabaseClient';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at top right, #1d2127, #0d1117)',
      color: 'var(--text-primary)',
      fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        padding: '40px',
        background: 'rgba(22, 27, 34, 0.8)',
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
        textAlign: 'center'
      }}>
        <div style={{ marginBottom: '32px' }}>
          <img src="/logo.png" alt="Disrupting Alpha" style={{ width: '64px', height: '64px', marginBottom: '20px', objectFit: 'contain' }} />
          <h1 style={{ 
            fontSize: '24px', 
            fontWeight: 700, 
            letterSpacing: '-0.02em',
            margin: '0 0 8px 0',
            background: 'linear-gradient(to right, #fff, #8b949e)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            DISRUPTING ALPHA
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
            Enter your credentials to access the terminal
          </p>
        </div>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ textAlign: 'left' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'var(--bg-primary)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                color: '#fff',
                fontSize: '14px',
                outline: 'none',
              }}
            />
          </div>

          <div style={{ textAlign: 'left' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'var(--bg-primary)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                color: '#fff',
                fontSize: '14px',
                outline: 'none',
              }}
            />
          </div>

          {error && (
            <div style={{ 
              padding: '10px', 
              background: 'rgba(248, 81, 73, 0.1)', 
              border: '1px solid var(--red)', 
              borderRadius: '6px',
              color: 'var(--red)',
              fontSize: '13px'
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '8px',
              padding: '12px',
              background: loading ? 'var(--bg-tertiary)' : 'var(--blue)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 4px 12px rgba(88, 166, 255, 0.2)'
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: '32px', borderTop: '1px solid var(--border)', paddingTop: '24px' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
            Secure access powered by Database Auth
          </p>
        </div>
      </div>
    </div>
  );
};
