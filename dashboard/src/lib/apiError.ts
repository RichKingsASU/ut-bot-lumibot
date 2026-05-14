export function toUserMessage(error: unknown): string {
  if (!error) return 'An unknown error occurred';
  const msg = error instanceof Error ? error.message : String(error);
  // Never expose internal implementation details to users
  if (msg.includes('supabase') || msg.includes('postgres') || msg.includes('query failed') ||
      msg.includes('statement timeout') || msg.includes('canceling statement')) {
    return 'Data could not be loaded. Please refresh or try again shortly.';
  }
  if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed to fetch')) {
    return 'Connection error. Check your internet connection and try again.';
  }
  if (msg.includes('401') || msg.includes('unauthorized')) {
    if (msg.includes('Alpaca')) return 'Alpaca API credentials invalid or expired.';
    return 'Authentication failed or session expired.';
  }
  return 'Something went wrong. Please try again.';
}
