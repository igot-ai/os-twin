/**
 * Extract a plan markdown document from an AI response.
 *
 * The AI may return the plan:
 *   1. Wrapped in a ```markdown / ```md / ``` fenced code block
 *   2. As raw text starting with "# Plan:"
 *   3. Preceded by conversational text before "# Plan:"
 *   4. As plain unstructured content (fallback)
 *
 * Plan content itself may contain nested code fences (e.g. ```text lifecycle
 * blocks), so strategy 1 uses depth-tracking instead of a greedy regex to
 * correctly identify the outer closing fence.
 */
export function extractPlan(content: string): string {
  // Strategy 1: Extract from a ```markdown / ```md / ``` fenced code block.
  // Must track fence depth to handle nested code blocks (e.g. ```text lifecycle blocks).
  const lines = content.split('\n');
  let startIdx = -1;
  let endIdx = -1;
  let depth = 0;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (startIdx === -1) {
      // Accept ```markdown, ```md, or plain ``` (if followed by # Plan: content)
      if (trimmed === '```markdown' || trimmed === '```md' || trimmed === '```') {
        startIdx = i + 1;
        depth = 1;
      }
    } else {
      if (/^```\w/.test(trimmed)) {
        // Opening of a nested code block (e.g., ```text, ```yaml)
        depth++;
      } else if (trimmed === '```') {
        depth--;
        if (depth === 0) { endIdx = i; break; }
      }
    }
  }
  if (startIdx !== -1 && endIdx !== -1) {
    return lines.slice(startIdx, endIdx).join('\n').trim();
  }

  // Strategy 2: Content starts with plan header
  if (content.trim().startsWith('# Plan:')) return content.trim();

  // Strategy 3: Find plan header anywhere in the content
  const planMatch = content.match(/(# Plan:[\s\S]*)/);
  if (planMatch) return planMatch[1].trim();

  return content;
}
