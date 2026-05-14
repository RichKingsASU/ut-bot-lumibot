import React, { useState } from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';

const colors = {
  red: '#f85149',
  border: '#30363d',
  bgTertiary: '#21262d',
};

export function EmergencyShutdown() {
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const handleFlatten = async () => {
    if (!confirmed) {
      setConfirmed(true);
      setTimeout(() => setConfirmed(false), 5000); // Reset after 5s
      return;
    }

    setLoading(true);
    try {
      const adminKey = localStorage.getItem('admin_api_key') || '';
      const response = await fetch('/.netlify/functions/alpaca-flatten', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-API-Key': adminKey
        }
      });

      if (response.ok) {
        alert('Emergency shutdown initiated successfully. All orders cancelled and positions closed.');
      } else {
        const data = await response.json();
        alert(`Shutdown failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    } finally {
      setLoading(false);
      setConfirmed(false);
    }
  };

  return (
    <button
      onClick={handleFlatten}
      disabled={loading}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 16px',
        borderRadius: 6,
        backgroundColor: confirmed ? colors.red : colors.bgTertiary,
        border: `1px solid ${confirmed ? colors.red : colors.border}`,
        color: confirmed ? '#fff' : colors.red,
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
    >
      {loading ? (
        <Loader2 size={16} className="animate-spin" />
      ) : (
        <ShieldAlert size={16} />
      )}
      {confirmed ? 'CONFIRM SHUTDOWN' : 'EMERGENCY SHUTDOWN'}
    </button>
  );
}
