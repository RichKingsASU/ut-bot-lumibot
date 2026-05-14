/**
 * Safely parse a timestamp that may be in seconds or milliseconds.
 * Returns a Date object. Never throws.
 */
export function parseTimestamp(value: number | string | null | undefined): Date | null {
  if (value == null) return null;
  const n = typeof value === 'string' ? Number(value) : value;
  if (isNaN(n)) return null;
  // Unix seconds are ~10 digits; ms are ~13 digits
  const ms = n < 1e12 ? n * 1000 : n;
  return new Date(ms);
}

export function formatTimestamp(
  value: number | string | null | undefined,
  opts?: Intl.DateTimeFormatOptions
): string {
  const d = parseTimestamp(value);
  if (!d) return '—';
  return d.toLocaleString(
    undefined,
    opts ?? {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }
  );
}
