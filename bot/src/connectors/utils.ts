
/**
 * Common utility functions for bot connectors.
 */

/**
 * Converts single *bold* to **bold** (useful for Discord from generic markdown).
 */
export function mdConvert(text: string): string {
  return text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '**$1**');
}

/**
 * Chunks text into multiple strings based on a limit, attempting to split at newlines or spaces.
 */
export function chunk(text: string, limit: number): string[] {
  if (!text) return [''];
  if (text.length <= limit) return [text];

  const chunks: string[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    if (remaining.length <= limit) {
      chunks.push(remaining);
      break;
    }

    let split = remaining.lastIndexOf('\n', limit);
    if (split === -1) {
      split = remaining.lastIndexOf(' ', limit);
    }
    if (split === -1) {
      split = limit;
    }

    chunks.push(remaining.slice(0, split));
    remaining = remaining.slice(split).trimStart();
  }

  return chunks;
}
