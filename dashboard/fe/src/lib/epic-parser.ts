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
  title: string;                          // Text after " — " or " - " dash in heading
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
  const match = line.match(/^(\s*- \[[ (x| )]\]\s+)(?:(TASK-\d+)|(\*\*)(T-.*?)(\*\*))?(\s*[:—-]\s*|\s+)?(.*)$/);
  if (!match) return null;
  return {
    prefix: match[1],
    idPrefix: match[3] || '',
    id: match[2] || match[4],
    idSuffix: match[5] || '',
    delimiter: match[6] || '',
    title: match[7],
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
  const epicHeadingRegex = /^#{2,3}\s+(EPIC-\d+)\s*[—-]\s*(.*)$/;
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
  const match = headingLine.match(/^#{2,3}\s+(EPIC-\d+)\s*[—-]\s*(.*)$/);
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
      currentSection = {
        heading: sectionMatch[1],
        headingLevel: line.startsWith('####') ? 4 : 3,
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
        frontmatter.set(key, metadataMatch[2].trim());
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
  
  // Check if it's a task list
  const isTasklist = lines.some(l => l.trim().match(/^- \[[ x]\] (TASK-\d+|\*\*T-.*\*\*)/));
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

  // Check if it's a checklist
  const isChecklist = lines.some(l => l.trim().match(/^- \[[ x]\]/));
  if (isChecklist) {
    section.type = 'checklist';
    section.items = [];
    let collectingPostamble = false;
    let inCodeBlock = false;

    for (const line of lines) {
      if (line.trim().startsWith('```')) {
          inCodeBlock = !inCodeBlock;
      }
      const itemHeader = inCodeBlock ? null : parseCheckItem(line);
      if (itemHeader) {
        section.items.push({
          text: itemHeader.text,
          checked: itemHeader.checked,
          rawLine: line,
          prefix: itemHeader.prefix,
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

  // Track what needs to be added if not found in any preamble/postamble
  const pendingKeys = new Set(epic.frontmatter.keys());
  let dependsOnPending = epic.depends_on.length > 0;

  // Scan all sections to see what's already there (even if it needs patching)
  for (const section of epic.sections) {
    const allLines = [...section.preamble, ...section.postamble];
    for (const line of allLines) {
      const metadataMatch = line.match(/^\*\*(.*?)\*\*[:]?\s*(.*)$/) || 
                          line.match(/^(Roles?|Working_dir|Objective|Skills):\s*(.*)$/i);
      if (metadataMatch) {
        let key = metadataMatch[1].trim();
        if (key.endsWith(':')) key = key.slice(0, -1);
        pendingKeys.delete(key);
      }
      if (line.trim().startsWith('depends_on:') || line.trim().startsWith('```yaml')) {
        dependsOnPending = false;
      }
    }
  }

  // Clone sections so we can modify them without side effects
  const sections = epic.sections.map(s => ({...s}));

  // If there are pending metadata or depends_on, add them to the first section
  if (pendingKeys.size > 0 || dependsOnPending) {
    if (sections.length === 0) {
      sections.push({
        heading: '',
        headingLevel: 0,
        type: 'text',
        content: '',
        rawLines: [],
        preamble: [],
        postamble: []
      });
    }

    const addedLines: string[] = [];
    for (const key of pendingKeys) {
      addedLines.push(`**${key}**: ${epic.frontmatter.get(key)}`);
    }
    if (dependsOnPending) {
      addedLines.push(`depends_on: [${epic.depends_on.join(', ')}]`);
    }
    
    // Insert at the beginning of the first section's preamble
    sections[0].preamble = [...addedLines, ...sections[0].preamble];
  }

  for (const section of sections) {
    lines.push(serializeSection(section, epic));
  }

  return lines.join('\n');
}

function serializeSection(section: EpicSection, epic: EpicNode): string {
  const resultLines: string[] = [];
  
  let preamble = [...section.preamble];
  // Ensure heading is present if it's not an implicit section
  if (section.heading && (preamble.length === 0 || !preamble[0].includes(section.heading))) {
    const prefix = '#'.repeat(section.headingLevel || 3);
    preamble = [`${prefix} ${section.heading}`, ...preamble];
  }

  // 1. Preamble with metadata and depends_on patching
  resultLines.push(...patchLines(preamble, epic));

  // 2. Structured list content
  if (section.type === 'tasklist' && section.tasks) {
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
  } else if (section.type === 'checklist' && section.items) {
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

  // 3. Postamble with metadata and depends_on patching
  resultLines.push(...patchLines(section.postamble, epic));

  return resultLines.join('\n');
}

function patchLines(lines: string[], epic: EpicNode): string[] {
  let result = patchMetadata(lines, epic);
  result = patchDependsOn(result, epic);
  return result;
}

function patchMetadata(lines: string[], epic: EpicNode): string[] {
  const result = [...lines];
  for (let i = 0; i < result.length; i++) {
    const line = result[i];
    const metadataMatch = line.match(/^\*\*(.*?)\*\*[:]?\s*(.*)$/) || line.match(/^(Roles?|Working_dir|Objective|Skills):\s*(.*)$/i);
    if (metadataMatch) {
      let key = metadataMatch[1].trim();
      if (key.endsWith(':')) key = key.slice(0, -1);
      const newValue = epic.frontmatter.get(key);
      if (newValue !== undefined && newValue !== metadataMatch[2].trim()) {
        const isBold = line.startsWith('**');
        const colonInside = line.includes(':**');
        const colonOutside = !colonInside && line.includes('**:');
        if (isBold) {
          if (colonInside) {
            result[i] = `**${key}:** ${newValue}`;
          } else if (colonOutside) {
            result[i] = `**${key}**: ${newValue}`;
          } else {
            result[i] = `**${key}** ${newValue}`;
          }
        } else {
          result[i] = `${key}: ${newValue}`;
        }
      }
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
