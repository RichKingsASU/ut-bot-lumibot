import React, { useState, useRef, useCallback } from 'react';
import { ShieldAlert, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { netlifyFetch } from '../../../lib/apiClient';

/**
 * Emergency Shutdown — double-action safety control.
 *
 * Stage 1: Click to arm (button turns red, starts 5s countdown).
 * Stage 2: Hold for 1 second to confirm (progress bar fills).
 *
 * This prevents accidental triggers while remaining fast for urgent use.
 * Human-in-the-loop is non-negotiable for anything that moves money.
 */
export function EmergencyShutdown() {
  const [loading, setLoading] = useState(false);
  const [armed, setArmed] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const holdTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const disarmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const HOLD_DURATION_MS = 1000;
  const HOLD_TICK_MS = 50;
  const DISARM_TIMEOUT_MS = 5000;

  const clearHold = useCallback(() => {
    if (holdTimerRef.current) {
      clearInterval(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    setHoldProgress(0);
  }, []);

  const executeShutdown = useCallback(async () => {
    clearHold();
    setLoading(true);
    try {
      const response = await netlifyFetch('alpaca-flatten', { method: 'POST' });

      if (response.ok) {
        alert('Emergency shutdown initiated. All orders cancelled, positions flattened.');
      } else {
        const data = await response.json();
        alert(`Shutdown failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    } finally {
      setLoading(false);
      setArmed(false);
    }
  }, [clearHold]);

  const handleClick = () => {
    if (loading) return;
    if (!armed) {
      setArmed(true);
      // Auto-disarm after 5s if no confirmation
      disarmTimerRef.current = setTimeout(() => {
        setArmed(false);
        clearHold();
      }, DISARM_TIMEOUT_MS);
    }
  };

  const handlePointerDown = () => {
    if (!armed || loading) return;
    let elapsed = 0;
    holdTimerRef.current = setInterval(() => {
      elapsed += HOLD_TICK_MS;
      const pct = Math.min(100, (elapsed / HOLD_DURATION_MS) * 100);
      setHoldProgress(pct);
      if (elapsed >= HOLD_DURATION_MS) {
        if (disarmTimerRef.current) clearTimeout(disarmTimerRef.current);
        executeShutdown();
      }
    }, HOLD_TICK_MS);
  };

  const handlePointerUp = () => {
    clearHold();
  };

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        onPointerDown={armed ? handlePointerDown : undefined}
        onPointerUp={armed ? handlePointerUp : undefined}
        onPointerLeave={armed ? handlePointerUp : undefined}
        disabled={loading}
        aria-label={armed ? 'Hold to confirm emergency shutdown' : 'Emergency shutdown'}
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-200 border relative overflow-hidden select-none",
          armed
            ? "bg-destructive text-destructive-foreground border-destructive shadow-[0_0_16px_rgba(239,68,68,0.4)]"
            : "bg-secondary text-[#ef4444] border-border hover:bg-destructive/10 hover:border-destructive/40"
        )}
      >
        {/* Hold progress bar */}
        {armed && holdProgress > 0 && (
          <div
            className="absolute inset-0 bg-white/20 transition-none"
            style={{ width: `${holdProgress}%` }}
            aria-hidden="true"
          />
        )}
        <span className="relative z-10 flex items-center gap-2">
          {loading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : armed ? (
            <AlertTriangle size={14} />
          ) : (
            <ShieldAlert size={14} />
          )}
          {loading
            ? 'FLATTENING…'
            : armed
              ? 'HOLD TO CONFIRM'
              : 'KILL SWITCH'}
        </span>
      </button>
    </div>
  );
}
