/**
 * agent_signals.confidence is stored as categorical text ("LOW" | "MEDIUM" |
 * "HIGH") by the signal agent, but the UI renders it as a 0-1 fraction
 * (multiplied by 100). Doing Number("MEDIUM") yields NaN → "NaN%" in the UI.
 *
 * parseConfidence normalizes any of: categorical text, a numeric string, a
 * 0-1 float, or a 0-100 number, into a 0-1 fraction. Unknown/empty → 0.5.
 */
export function parseConfidence(raw: unknown): number {
  if (typeof raw === "number" && !Number.isNaN(raw)) {
    return raw > 1 ? raw / 100 : raw;
  }
  if (typeof raw === "string") {
    const s = raw.trim().toUpperCase();
    const categorical: Record<string, number> = { LOW: 0.34, MEDIUM: 0.67, HIGH: 1.0 };
    if (s in categorical) return categorical[s];
    const n = parseFloat(s);
    if (!Number.isNaN(n)) return n > 1 ? n / 100 : n;
  }
  return 0.5;
}
