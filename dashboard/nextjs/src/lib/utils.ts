/**
 * Escape HTML special characters to prevent XSS
 */
export function esc(s: string | null | undefined): string {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Truncate a string to n characters, appending ellipsis if needed
 */
export function trunc(s: string | null | undefined, n: number): string {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

/**
 * Format an ISO timestamp to HH:MM:SS
 */
export function fmtTime(ts: string | null | undefined): string {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString('en', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(ts).slice(11, 19);
  }
}
