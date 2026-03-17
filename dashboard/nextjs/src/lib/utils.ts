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
 * Format an ISO timestamp or Unix epoch to HH:MM:SS
 * Returns empty string for null/undefined, never returns 'Invalid Date'.
 */
export function fmtTime(ts: string | null | undefined): string {
  if (!ts) return '';
  let d: Date;
  // Check if it's a Unix epoch (numeric only string)
  if (/^\d{9,13}$/.test(ts.trim())) {
    // 9-10 digits = seconds, 13 digits = millis
    const n = Number(ts.trim());
    d = new Date(ts.trim().length >= 13 ? n : n * 1000);
  } else {
    d = new Date(ts);
  }
  if (!isNaN(d.getTime())) {
    return d.toLocaleTimeString('en', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }
  // Fallback: try to pull HH:MM:SS from string directly (e.g. "03/16/26 22:39:19")
  const m = String(ts).match(/(\d{2}:\d{2}:\d{2})/);
  if (m) return m[1];
  return '';
}
