import React, { useState } from 'react';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { cn } from '../../../lib/utils';

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
      const adminKey = localStorage.getItem('ADMIN_API_KEY') || localStorage.getItem('admin_api_key') || '';
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
      aria-label={confirmed ? 'Confirm emergency shutdown' : 'Emergency shutdown'}
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-200 border",
        confirmed
          ? "bg-destructive text-destructive-foreground border-destructive shadow-[0_0_12px_rgba(239,68,68,0.3)]"
          : "bg-secondary text-[#ef4444] border-border hover:bg-destructive/10 hover:border-destructive/40"
      )}
    >
      {loading ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <ShieldAlert size={14} />
      )}
      {confirmed ? 'CONFIRM' : 'KILL SWITCH'}
    </button>
  );
}
