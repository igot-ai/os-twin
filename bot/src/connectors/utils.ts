
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

/**
 * Detects an EPIC-NNN reference in a string.
 */
export function detectEpicRef(text: string): string | undefined {
  if (!text) return undefined;
  const match = text.match(/EPIC-(\d+)/i);
  return match ? match[0].toUpperCase() : undefined;
}

/**
 * Guesses asset type from filename and MIME type.
 */
export function guessAssetType(filename: string, mimeType?: string): string {
  const nameLower = filename.toLowerCase();
  const mimeLower = (mimeType || '').toLowerCase();

  // Design mockups
  if (mimeLower.startsWith('image/') || ['.fig', '.sketch', '.xd', '.psd', '.ai'].some(ext => nameLower.includes(ext))) {
    if (['mockup', 'design', 'wireframe', 'ui', 'ux'].some(kw => nameLower.includes(kw))) {
      return 'design-mockup';
    }
    if (mimeLower.startsWith('image/')) {
      return 'design-mockup';
    }
  }

  // API specs
  if (['api', 'spec', 'openapi', 'swagger', 'graphql', 'proto'].some(kw => nameLower.includes(kw))) {
    return 'api-spec';
  }
  if ((nameLower.endsWith('.yaml') || nameLower.endsWith('.yml')) && nameLower.includes('spec')) {
    return 'api-spec';
  }

  // Test data
  if (['test', 'fixture', 'sample', 'seed'].some(kw => nameLower.includes(kw))) {
    return 'test-data';
  }
  if (nameLower.endsWith('.csv')) {
    return 'test-data';
  }

  // Config
  if (['config', '.env', 'setting'].some(kw => nameLower.includes(kw))) {
    return 'config';
  }
  if (['.env', '.ini', '.toml', '.cfg'].some(ext => nameLower.endsWith(ext))) {
    return 'config';
  }

  // Reference docs
  if (['.md', '.txt', '.pdf', '.doc', '.docx', '.rtf'].some(ext => nameLower.endsWith(ext))) {
    return 'reference-doc';
  }

  // Media
  if (mimeLower.startsWith('video/') || mimeLower.startsWith('audio/')) {
    return 'media';
  }

  return 'other';
}

/**
 * Detect if a message is a system/status query rather than a plan refinement.
 * Used to route @mentions to askAgent() even when in editing mode.
 */
const AGENT_QUERY_PATTERNS = [
  /\b(is|are|does|has)\b.+\b(plan|room|war-?room|epic|agent|bot|system)\b.+\b(running|active|done|pass|fail|finish|complet|start|launch|stop)\b/i,
  /\b(status|progress|health|running|launched?|failed?|errors?)\b.*\b(plan|room|war-?room|epic|agent)\b/i,
  /\b(plan|room|war-?room|epic|agent)\b.*\b(status|progress|health|running|launched?|failed?|errors?)\b/i,
  /\bwhat(?:'s| is| are)\b.+\b(status|progress|running|happening)\b/i,
  /\bhow(?:'s| is| are)\b.+\b(plan|room|war-?room|epic|progress)\b/i,
  /\b(list|show|check)\b.+\b(plan|room|war-?room|epic|skill|role)\b/i,
  /\b(search|find|install|remove)\b.+\bskill/i,
];

export function isAgentQuery(text: string): boolean {
  return AGENT_QUERY_PATTERNS.some((re) => re.test(text));
}

