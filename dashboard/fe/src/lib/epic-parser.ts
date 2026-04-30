/**
 * Epic Markdown Parser & Serializer
 *
 * This module provides functions to parse EPIC-style markdown into a structured AST
 * (EpicDocument) and serialize it back to markdown with 100% round-trip fidelity.
 */

// ── AST Types ─────────────────────────────────────

export interface EpicDocument {
  title: string;                          // H1 line: "# PLAN: ..."
  preamble: string;                       // Content between H1 and first EPIC (Goal, Config, etc.)
  epics: EpicNode[];
  postamble: string;                      // Content after last EPIC (Verification Plan, etc.)
}

export interface EpicNode {
  ref: string;                            // "EPIC-001"
  title: string;                          // Text after " — ", " - ", or ": " in heading
  headingLevel: number;                   // 2 for ##, 3 for ###
  rawHeading: string;                     // Full heading line for exact reproduction
  frontmatter: Map<string, string>;       // **Key:** Value or Key: Value pairs
  sections: EpicSection[];                // Ordered sections preserving original structure
  depends_on: string[];                   // Extracted from YAML block or inline
  rawDependsOn: string;                   // Original depends_on block text for round-trip
}

export type SectionType = 'text' | 'checklist' | 'tasklist';

export interface EpicSection {
  heading: string;                        // "Description", "Definition of Done", "Tasks", "Acceptance Criteria", etc.
  headingLevel: number;
  sectionKey: string;                     // Stable lowercase identifier: "definition_of_done", "acceptance_criteria", "tasks", etc.
  type: SectionType;                      // Inferred from content
  content: string;                        // Raw content for 'text' type (including lines before/after lists)
  items?: CheckItem[];                    // For 'checklist' type (DoD, AC)
  tasks?: TaskNode[];                     // For 'tasklist' type
  rawLines: string[];                     // Original lines for exact reproduction (fallback)
  preamble: string[];                     // Lines before the first list item
  postamble: string[];                    // Lines after the last list item
}

export interface CheckItem {
  text: string;
  checked: boolean;
  rawLine: string;                        // Original line for exact reproduction
  prefix: string;                         // Indentation and checkbox: e.g., "- [ ] "
}

export interface TaskNode {
  id: string;                             // "T-G001.1" or "TASK-001"
  title: string;                          // Text after " — " or " - " in the task line
  completed: boolean;
  body: string;                           // Everything after the task header line (may include code blocks)
  bodyLines: string[];                    // Original lines of the body for exact reproduction
  rawHeader: string;                      // Original first line for exact reproduction
  prefix: string;                         // e.g., "- [ ] "
  idPrefix: string;                       // e.g., "**"
  idSuffix: string;                       // e.g., "**"
  delimiter: string;                      // e.g., " — " or ": "
}

// ── Helpers ────────────────────────────────────────

/** Convert a section heading to a stable lowercase key (e.g. "Acceptance Criteria" → "acceptance_criteria"). */
export function headingToSectionKey(heading: string): string {
  return heading
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')   // non-alphanumeric → underscore
    .replace(/^_|_$/g, '');         // strip leading/trailing underscores
}

/** Known section keys for standard EPIC sections (used for type inference). */
const CHECKLIST_SECTION_KEYS = new Set([
  'definition_of_done', 'dod', 'acceptance_criteria', 'ac', 'criteria',
]);

/** Known section keys for task-list sections. */
const TASKLIST_SECTION_KEYS = new Set([
  'tasks',
  'task',
]);

/**
 * Find a section in an epic by its sectionKey (case-insensitive lookup).
 * Returns the first matching section, or undefined if not found.
 */
export function findSectionByKey(epic: EpicNode, key: string): EpicSection | undefined {
  const normalizedKey = headingToSectionKey(key);
  return epic.sections.find(s => s.sectionKey === normalizedKey);
}

/**
 * Find a section in an epic by its heading (case-insensitive).
 * Returns the first matching section, or undefined if not found.
 */
export function findSectionByHeading(epic: EpicNode, heading: string): EpicSection | undefined {
  const targetKey = headingToSectionKey(heading);
  return epic.sections.find(s => s.sectionKey === targetKey);
}

function parseDependsOn(text: string): string[] {
  // Handle inline [A, B]
  const inlineMatch = text.match(/depends_on:\s*\[(.*)\]/);
  if (inlineMatch) {
    return inlineMatch[1].split(',').map(s => s.trim().replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1')).filter(s => s);
  }
  // Handle multi-line
  const lines = text.split(/\r?\n/);
  const result: string[] = [];
  let inList = false;
  for (const line of lines) {
    if (line.trim().startsWith('depends_on:')) {
      inList = true;
      continue;
    }
    if (inList) {
      const itemMatch = line.match(/^\s*-\s*(.*)$/);
      if (itemMatch) {
        result.push(itemMatch[1].trim().replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1'));
      } else if (line.trim() === '' || line.match(/^\s*\w+:/)) {
        // End of list or next field
        break;
      }
    }
  }
  return result;
}

function parseTaskHeader(line: string) {
  const match = line.match(/^(\s*- \[[ (x| )]\]\s+)(?:(\*\*)?(TASK-[\w.-]+|T-[\w.-]+)(\*\*)?)?(\s*[:—-]\s*|\s+)?(.*)$/);
  if (!match) return null;
  return {
    prefix: match[1],
    idPrefix: match[2] || '',
    id: match[3] || '',
    idSuffix: match[4] || '',
    delimiter: match[5] || '',
    title: match[6],
    completed: line.trim().startsWith('- [x]'),
  };
}

function parseCheckItem(line: string) {
  const match = line.match(/^(\s*- \[[ (x| )]\]\s+)(.*)$/);
  if (!match) return null;
  return {
    prefix: match[1],
    text: match[2],
    checked: line.trim().startsWith('- [x]'),
  };
}

// ── Parser ────────────────────────────────────────

/**
 * Parses a markdown string into an EpicDocument AST.
 */
export function parseEpicMarkdown(md: string): EpicDocument {
  const lines = md.split(/\r?\n/);
  const epics: EpicNode[] = [];
  let title = '';
  
  // Find the H1 title
  const titleLineIndex = lines.findIndex(l => l.startsWith('# '));
  if (titleLineIndex !== -1) {
    title = lines[titleLineIndex];
  }

  // Find EPIC boundaries
  const epicHeadingRegex = /^#{2,3}\s+(EPIC-\d+)\s*[—\-:]\s*(.*)$/;
  const epicIndices: number[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].match(epicHeadingRegex)) {
      epicIndices.push(i);
    }
  }

  if (epicIndices.length === 0) {
    return { title, preamble: md, epics: [], postamble: '' };
  }

  const preamble = lines.slice(titleLineIndex !== -1 ? titleLineIndex + 1 : 0, epicIndices[0]).join('\n');
  
  const lastEpicIndex = epicIndices[epicIndices.length - 1];
  const lastEpicHeadingLevel = lines[lastEpicIndex].startsWith('###') ? 3 : 2;
  let lastEpicEnd = lines.length;
  for (let i = lastEpicIndex + 1; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('# ') || 
        line.startsWith('## ') || 
        (lastEpicHeadingLevel === 3 && line.startsWith('### '))) {
      if (!line.match(epicHeadingRegex)) {
        lastEpicEnd = i;
        break;
      }
    }
  }

  for (let i = 0; i < epicIndices.length; i++) {
    const start = epicIndices[i];
    const end = i < epicIndices.length - 1 ? epicIndices[i + 1] : lastEpicEnd;
    epics.push(parseEpicNode(lines.slice(start, end)));
  }

  const postamble = lines.slice(lastEpicEnd).join('\n');

  return { title, preamble, epics, postamble };
}

function parseEpicNode(lines: string[]): EpicNode {
  const headingLine = lines[0];
  const match = headingLine.match(/^#{2,3}\s+(EPIC-\d+)\s*[—\-:]\s*(.*)$/);
  const ref = match?.[1] || '';
  const title = match?.[2] || '';
  const headingLevel = headingLine.startsWith('###') ? 3 : 2;

  const frontmatter = new Map<string, string>();
  const sections: EpicSection[] = [];
  let depends_on: string[] = [];
  let rawDependsOn = '';

  let currentSection: EpicSection | null = null;
  let sectionLines: string[] = [];

  const flushSection = () => {
    if (currentSection) {
      processSectionContent(currentSection, sectionLines);
      sections.push(currentSection);
      currentSection = null;
      sectionLines = [];
    }
  };

  let inYaml = false;
  let inCodeBlock = false;
  let yamlBlockLines: string[] = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    const sectionMatch = line.match(/^#{3,4}\s+(.*)$/);
    const metadataMatch = line.match(/^\*\*(.*?)\*\*[:]?\s*(.*)$/) || line.match(/^(Roles?|Working_dir|Objective|Skills):\s*(.*)$/i);

    if (line.trim().startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        if (line.trim().startsWith('```yaml')) {
          inYaml = true;
          yamlBlockLines = [line];
        }
      } else {
        inCodeBlock = false;
        if (inYaml) {
          inYaml = false;
          yamlBlockLines.push(line);
          const yamlContent = yamlBlockLines.join('\n');
          const deps = parseDependsOn(yamlContent);
          if (deps.length > 0 || yamlContent.includes('depends_on:')) {
            depends_on = deps;
            rawDependsOn = yamlContent;
          }
        }
      }
    } else if (inYaml) {
      yamlBlockLines.push(line);
    }

    if (sectionMatch && !inCodeBlock) {
      flushSection();
      const headingText = sectionMatch[1];
      const sectionKey = headingToSectionKey(headingText);
      currentSection = {
        heading: headingText,
        headingLevel: line.startsWith('####') ? 4 : 3,
        sectionKey,
        type: 'text',
        content: '',
        rawLines: [],
        preamble: [],
        postamble: [],
      };
      sectionLines = [line];
    } else {
      if (!currentSection) {
        // Create an implicit section for frontmatter/metadata
        currentSection = {
          heading: '',
          headingLevel: 0,
          sectionKey: '',
          type: 'text',
          content: '',
          rawLines: [],
          preamble: [],
          postamble: [],
        };
        sectionLines = [];
      }
      sectionLines.push(line);

      if (metadataMatch && !inCodeBlock) {
        let key = metadataMatch[1].trim();
        if (key.endsWith(':')) key = key.slice(0, -1);
        let value = metadataMatch[2].trim();
        // Normalize Roles: strip @ prefixes, unify separators to comma
        if (/^Roles?$/i.test(key)) {
          value = value.split(/[,\s]+/).filter(Boolean).map(r => r.replace(/^@/, '')).filter(r => r && r !== '...').join(', ');
        }
        frontmatter.set(key, value);
      }

      if (line.trim().startsWith('depends_on:') && !inCodeBlock) {
        rawDependsOn = line;
        depends_on = parseDependsOn(line);
      }
    }
  }
  flushSection();

  return {
    ref,
    title,
    headingLevel,
    rawHeading: headingLine,
    frontmatter,
    sections,
    depends_on,
    rawDependsOn,
  };
}

function processSectionContent(section: EpicSection, lines: string[]) {
  section.rawLines = lines;
  section.content = lines.join('\n');
  section.preamble = [];
  section.postamble = [];

  // Use sectionKey to determine the expected type for known sections
  const isKnownTasklist = TASKLIST_SECTION_KEYS.has(section.sectionKey);
  const isKnownChecklist = CHECKLIST_SECTION_KEYS.has(section.sectionKey);

  // Check if it's a task list
  const isTasklist = isKnownTasklist || lines.some(l => l.trim().match(/^- \[[ x]\] (\*\*)?(TASK-[\w.-]+|T-[\w.-]+)(\*\*)?/));
  if (isTasklist) {
    section.type = 'tasklist';
    section.tasks = [];
    let currentTask: TaskNode | null = null;
    let taskBodyLines: string[] = [];
    let collectingPostamble = false;
    let inCodeBlock = false;

    for (const line of lines) {
      if (line.trim().startsWith('```')) {
          inCodeBlock = !inCodeBlock;
      }

      const taskHeader = inCodeBlock ? null : parseTaskHeader(line);
      if (taskHeader && taskHeader.id) {
        if (currentTask) {
          currentTask.body = taskBodyLines.join('\n');
          currentTask.bodyLines = taskBodyLines;
          section.tasks.push(currentTask);
        }
        currentTask = {
          id: taskHeader.id,
          title: taskHeader.title,
          completed: taskHeader.completed,
          body: '',
          bodyLines: [],
          rawHeader: line,
          prefix: taskHeader.prefix,
          idPrefix: taskHeader.idPrefix,
          idSuffix: taskHeader.idSuffix,
          delimiter: taskHeader.delimiter,
        };
        taskBodyLines = [];
        collectingPostamble = false;
      } else {
        if (currentTask) {
          if (!inCodeBlock && (line.trim().startsWith('depends_on:') || line.trim() === '---')) {
            collectingPostamble = true;
          }

          if (collectingPostamble) {
            section.postamble.push(line);
          } else {
            taskBodyLines.push(line);
          }
        } else {
          section.preamble.push(line);
        }
      }
    }
    if (currentTask) {
      currentTask.body = taskBodyLines.join('\n');
      currentTask.bodyLines = taskBodyLines;
      section.tasks.push(currentTask);
    }
    return;
  }

  // Check if it's a checklist: either has checkbox items, or is a known checklist
  // section that uses plain `- Item` syntax (without `[ ]` checkboxes)
  const hasCheckboxItems = lines.some(l => l.trim().match(/^- \[[ x]\]/));
  const hasPlainItems = isKnownChecklist && lines.some(l => l.trim().match(/^- [^\[]/));

  if (hasCheckboxItems || hasPlainItems) {
    section.type = 'checklist';
    section.items = [];
    let collectingPostamble = false;
    let inCodeBlock = false;

    for (const line of lines) {
      if (line.trim().startsWith('```')) {
          inCodeBlock = !inCodeBlock;
      }
      const itemHeader = inCodeBlock ? null : parseCheckItem(line);
      // Also handle plain list items (without checkboxes) in known checklist sections
      const plainItemMatch = !itemHeader && !inCodeBlock && isKnownChecklist
        ? line.match(/^(\s*- )(.*)$/)
        : null;

      if (itemHeader) {
        section.items.push({
          text: itemHeader.text,
          checked: itemHeader.checked,
          rawLine: line,
          prefix: itemHeader.prefix,
        });
        collectingPostamble = false;
      } else if (plainItemMatch) {
        // Convert plain list item to a CheckItem (unchecked by default)
        section.items.push({
          text: plainItemMatch[2],
          checked: false,
          rawLine: line,
          prefix: plainItemMatch[1],
        });
        collectingPostamble = false;
      } else {
        if (section.items.length > 0) {
          if (!inCodeBlock && (line.trim().startsWith('depends_on:') || line.trim() === '---')) {
            collectingPostamble = true;
          }
          if (collectingPostamble) {
            section.postamble.push(line);
          } else {
            section.postamble.push(line);
          }
        } else {
          section.preamble.push(line);
        }
      }
    }
    return;
  }

  section.type = 'text';
  section.preamble = lines;
}

/**
 * Serializes an EpicDocument AST back into a markdown string.
 */
export function serializeEpicMarkdown(doc: EpicDocument): string {
  const resultLines: string[] = [];

  if (doc.title) {
    const titleLine = doc.title.startsWith('# ') ? doc.title : `# ${doc.title}`;
    resultLines.push(titleLine);
  }

  if (doc.preamble !== undefined && doc.preamble !== '') {
    resultLines.push(doc.preamble);
  }

  for (const epic of doc.epics) {
    resultLines.push(serializeEpicNode(epic));
  }

  if (doc.postamble) {
    resultLines.push(doc.postamble);
  }

  return resultLines.join('\n');
}

function serializeEpicNode(epic: EpicNode): string {
  const lines: string[] = [];
  lines.push(epic.rawHeading);

  // Determine which frontmatter keys and depends_on have already been
  // placed inside a section's preamble/postamble so we don't duplicate them.
  const keysInSectionPreamble = new Set<string>();
  let dependsOnInPreamble = false;

  for (const section of epic.sections) {
    for (const line of [...section.preamble, ...section.postamble]) {
      const metadataMatch = line.match(/^\*\*(.*?)\*\*[:]?\s*(.*)$/) ||
                           line.match(/^(Roles?|Working_dir|Objective|Skills):\s*(.*)$/i);
      if (metadataMatch) {
        let key = metadataMatch[1].trim();
        if (key.endsWith(':')) key = key.slice(0, -1);
        keysInSectionPreamble.add(key);
      }
      if (line.trim().startsWith('depends_on:') || line.trim().startsWith('```yaml')) {
        dependsOnInPreamble = true;
      }
    }
  }

  // Clone sections so we can modify them without side effects
  const sections = epic.sections.map(s => ({...s, preamble: [...s.preamble], postamble: [...s.postamble]}));

  // Determine if we need to output depends_on
  // Output it if: (1) array has items, OR (2) rawDependsOn is non-empty (means it was present in original, even if empty array)
  const shouldOutputDependsOn = epic.depends_on.length > 0 || epic.rawDependsOn.length > 0;

  // Only strip depends_on and --- separators if we're going to output depends_on
  // This ensures we can place depends_on before any trailing ---
  // If there's no depends_on, preserve the original structure
  let hasTrailingSeparator = false;
  if (shouldOutputDependsOn) {
    hasTrailingSeparator = stripDependsOnFromSections(sections);
  }

  // Output frontmatter: emit any keys NOT already present in a section's preamble
  const pendingKeys = new Set(epic.frontmatter.keys());
  for (const key of keysInSectionPreamble) {
    pendingKeys.delete(key);
  }

  if (pendingKeys.size > 0) {
    // Add pending frontmatter to the first section's preamble
    if (sections.length === 0) {
      sections.push({
        heading: '',
        headingLevel: 0,
        sectionKey: '',
        type: 'text',
        content: '',
        rawLines: [],
        preamble: [],
        postamble: []
      });
    }

    const addedLines: string[] = [];
    for (const key of pendingKeys) {
      const value = epic.frontmatter.get(key)!;
      const displayValue = /^Roles?$/i.test(key) ? formatRolesValue(value) : value;
      addedLines.push(`**${key}**: ${displayValue}`);
    }

    // Insert at the beginning of the first section's preamble
    sections[0].preamble = [...addedLines, ...sections[0].preamble];
  }

  // Serialize each section
  for (const section of sections) {
    // Skip checklist/tasklist sections that have had all their items removed
    if ((section.type === 'checklist' && (!section.items || section.items.length === 0)) ||
        (section.type === 'tasklist' && (!section.tasks || section.tasks.length === 0))) {
      // Only skip if the section has no heading (implicit section) or has no
      // meaningful content beyond the empty list
      const hasContent = section.preamble.some(l => l.trim() !== '' && !l.match(/^#{3,4}\s/)) ||
                         section.postamble.some(l => l.trim() !== '' && !l.trim().startsWith('depends_on:'));
      if (!hasContent) continue;
    }

    const sectionStr = serializeSection(section, epic);
    // Split the section string into lines and add to our lines array
    const sectionLines = sectionStr.split('\n');
    lines.push(...sectionLines);
  }

  // Only strip trailing blank lines when we're about to add depends_on
  // (to make room for the depends_on line with a blank line before it)
  // For EPICs without depends_on, preserve the original trailing structure
  if (shouldOutputDependsOn) {
    while (lines.length > 0 && lines[lines.length - 1] === '') {
      lines.pop();
    }
  }
  
  // Append depends_on at the end of the EPIC block
  if (shouldOutputDependsOn) {
    lines.push('');
    lines.push(`depends_on: [${epic.depends_on.join(', ')}]`);
    // Add trailing blank line to separate from next EPIC
    lines.push('');
  }

  // Re-add the --- separator after depends_on if it was stripped
  // Only add a blank line before --- if the last line isn't already blank
  if (hasTrailingSeparator) {
    if (lines.length > 0 && lines[lines.length - 1] !== '') {
      lines.push('');
    }
    lines.push('---');
    lines.push('');  // Blank line after separator
  }

  return lines.join('\n');
}

/**
 * Strip depends_on lines, YAML blocks, and trailing --- separators from all section preambles/postambles.
 * This ensures depends_on is only emitted once, at the end of the EPIC block,
 * and --- separators are moved after depends_on.
 * Returns true if a trailing --- was stripped (so it can be re-added after depends_on).
 */
function stripDependsOnFromSections(sections: EpicSection[]): boolean {
  let hasTrailingSeparator = false;
  for (const section of sections) {
    const { stripped: strippedPreamble } = removeDependsOnLines(section.preamble);
    section.preamble = strippedPreamble;
    
    const { stripped: strippedPostamble, hadSeparator } = removeDependsOnLines(section.postamble);
    section.postamble = strippedPostamble;
    if (hadSeparator) {
      hasTrailingSeparator = true;
    }
  }
  return hasTrailingSeparator;
}

/**
 * Remove depends_on lines and fenced YAML blocks containing depends_on from a lines array.
 * Only treats --- as a trailing separator if it appears after depends_on (or at the very end with no depends_on).
 * Preserves --- lines that are followed by other content.
 * Returns the filtered lines and whether a trailing --- separator was removed.
 */
function removeDependsOnLines(lines: string[]): { stripped: string[]; hadSeparator: boolean } {
  const result: string[] = [];
  let inCodeBlock = false;
  let inYamlBlock = false;
  let yamlStart = -1;
  let hadSeparator = false;
  
  // Track the last non-empty line index to detect if --- is truly trailing
  let lastNonEmptyIndex = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (lines[i].trim() !== '') {
      lastNonEmptyIndex = i;
      break;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        if (line.trim().startsWith('```yaml')) {
          inYamlBlock = true;
          yamlStart = i;
        } else {
          result.push(line);
        }
      } else {
        inCodeBlock = false;
        if (inYamlBlock) {
          inYamlBlock = false;
          // Skip the closing ``` of the YAML block
          yamlStart = -1;
        } else {
          result.push(line);
        }
      }
      continue;
    }

    if (inYamlBlock) {
      // Skip YAML block content (will be replaced by inline depends_on at end)
      continue;
    }

    if (!inCodeBlock && line.trim().startsWith('depends_on:')) {
      // Skip inline depends_on lines
      continue;
    }

    // Only treat --- as a trailing separator if:
    // 1. It's not inside a code block
    // 2. It appears after a depends_on line OR it's the last non-empty content
    if (!inCodeBlock && line.trim() === '---') {
      // Check if this --- is followed by other non-empty content
      let hasContentAfter = false;
      for (let j = i + 1; j < lines.length; j++) {
        if (lines[j].trim() !== '' && lines[j].trim() !== '---') {
          hasContentAfter = true;
          break;
        }
      }
      
      if (!hasContentAfter) {
        // This is a trailing separator - skip it (will be re-added after depends_on)
        hadSeparator = true;
        continue;
      }
      // Otherwise keep the --- - it's followed by content
    }

    result.push(line);
  }

  return { stripped: result, hadSeparator };
}

/**
 * Create a new EpicSection suitable for adding to an EPIC.
 * This is the serializeNewSection helper from the epic brief.
 */
export function serializeNewSection(
  heading: string,
  headingLevel: number,
  type: SectionType,
  items?: CheckItem[],
  tasks?: TaskNode[],
  content?: string,
): EpicSection {
  const sectionKey = headingToSectionKey(heading);
  return {
    heading,
    headingLevel,
    sectionKey,
    type,
    content: content || '',
    rawLines: [],
    items: type === 'checklist' ? (items || []) : undefined,
    tasks: type === 'tasklist' ? (tasks || []) : undefined,
    preamble: [],
    postamble: [],
  };
}

function serializeSection(section: EpicSection, epic: EpicNode): string {
  const resultLines: string[] = [];

  let preamble = [...section.preamble];
  // Ensure heading is present if it's not an implicit section
  if (section.heading && (preamble.length === 0 || !preamble[0].includes(section.heading))) {
    const prefix = '#'.repeat(section.headingLevel || 3);
    preamble = [`${prefix} ${section.heading}`, ...preamble];
  }

  // 1. Preamble with metadata patching (depends_on already stripped)
  resultLines.push(...patchMetadata(preamble, epic));

  // 2. Structured list content — always serialize from AST arrays,
  //    which respects any reordering, additions, or removals.
  if (section.type === 'tasklist' && section.tasks && section.tasks.length > 0) {
    for (const task of section.tasks) {
      const checkbox = task.completed ? '[x]' : '[ ]';
      const prefix = task.prefix || '- [ ] ';
      const idPrefix = task.idPrefix || '';
      const idSuffix = task.idSuffix || '';
      const delimiter = task.delimiter || ' — ';

      const header = `${prefix.replace(/\[[ x]\]/, checkbox)}${idPrefix}${task.id}${idSuffix}${delimiter}${task.title}`;
      resultLines.push(header);

      const currentBody = task.bodyLines ? task.bodyLines.join('\n') : '';
      if (task.body !== currentBody && task.body !== '') {
          resultLines.push(task.body);
      } else if (task.bodyLines && task.bodyLines.length > 0) {
          resultLines.push(...task.bodyLines);
      }
    }
  } else if (section.type === 'checklist' && section.items && section.items.length > 0) {
    for (const item of section.items) {
      const checkbox = item.checked ? '[x]' : '[ ]';
      const prefix = item.prefix || '- [ ] ';
      const line = `${prefix.replace(/\[[ x]\]/, checkbox)}${item.text}`;
      resultLines.push(line);
    }
  } else if (section.type === 'text') {
    const fullText = [...preamble, ...section.postamble].join('\n');
    if (section.content && !fullText.includes(section.content)) {
      resultLines.push(section.content);
    }
  }

  // 3. Postamble with metadata patching (depends_on already stripped)
  resultLines.push(...patchMetadata(section.postamble, epic));

  return resultLines.join('\n');
}

function patchLines(lines: string[], epic: EpicNode): string[] {
  let result = patchMetadata(lines, epic);
  result = patchDependsOn(result, epic);
  return result;
}

/** Normalize a Roles value to bare comma-separated names (strip @, unify separators). */
function normalizeRolesValue(value: string): string {
  return value.split(/[,\s]+/).filter(Boolean).map(r => r.replace(/^@/, '')).filter(r => r && r !== '...').join(', ');
}

/** Format a bare Roles value with @ prefix for markdown output. */
function formatRolesValue(value: string): string {
  return value.split(/[,\s]+/).filter(Boolean).map(r => r.startsWith('@') ? r : `@${r}`).join(', ');
}

function patchMetadata(lines: string[], epic: EpicNode): string[] {
  const result: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const metadataMatch = line.match(/^\*\*(.*?)\*\*[:]?\s*(.*)$/) || line.match(/^(Roles?|Working_dir|Objective|Skills):\s*(.*)$/i);
    if (metadataMatch) {
      let key = metadataMatch[1].trim();
      if (key.endsWith(':')) key = key.slice(0, -1);

      // If the key was deleted from frontmatter, omit this line entirely
      if (!epic.frontmatter.has(key)) {
        continue;
      }

      const newValue = epic.frontmatter.get(key)!;

      // For Roles keys, compare normalized (bare) values to avoid
      // spurious rewrites when only the @ prefix differs.
      const isRolesKey = /^Roles?$/i.test(key);
      const oldNormalized = isRolesKey ? normalizeRolesValue(metadataMatch[2].trim()) : metadataMatch[2].trim();
      const newNormalized = isRolesKey ? normalizeRolesValue(newValue) : newValue;

      if (newNormalized !== oldNormalized) {
        const displayValue = isRolesKey ? formatRolesValue(newValue) : newValue;
        const isBold = line.startsWith('**');
        const colonInside = line.includes(':**');
        const colonOutside = !colonInside && line.includes('**:');
        if (isBold) {
          if (colonInside) {
            result.push(`**${key}:** ${displayValue}`);
          } else if (colonOutside) {
            result.push(`**${key}**: ${displayValue}`);
          } else {
            result.push(`**${key}** ${displayValue}`);
          }
        } else {
          result.push(`${key}: ${displayValue}`);
        }
      } else {
        result.push(line);
      }
    } else {
      result.push(line);
    }
  }
  return result;
}

function patchDependsOn(lines: string[], epic: EpicNode): string[] {
  const result = [...lines];
  let inCodeBlock = false;
  let inYaml = false;
  let yamlStart = -1;

  for (let i = 0; i < result.length; i++) {
    const line = result[i];
    if (line.trim().startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        if (line.trim().startsWith('```yaml')) {
          inYaml = true;
          yamlStart = i;
        }
      } else {
        inCodeBlock = false;
        if (inYaml) {
          inYaml = false;
          const block = result.slice(yamlStart, i + 1).join('\n');
          if (block.includes('depends_on:')) {
            const newContent = `depends_on: [${epic.depends_on.join(', ')}]`;
            const insertedLines = newContent.split('\n');
            result.splice(yamlStart + 1, i - yamlStart - 1, ...insertedLines);
            i = yamlStart + insertedLines.length + 1;
            if (i >= result.length) break;
          }
        }
      }
      continue;
    }

    if (!inCodeBlock && line.trim().startsWith('depends_on:')) {
      const hasQuotes = line.includes('"') || line.includes("'");
      const q = hasQuotes ? '"' : '';
      result[i] = `depends_on: [${epic.depends_on.map(d => `${q}${d}${q}`).join(', ')}]`;
    }
  }
  return result;
}
