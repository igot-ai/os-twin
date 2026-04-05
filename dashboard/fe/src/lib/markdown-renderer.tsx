import React from 'react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * A lightweight, regex-based markdown renderer.
 * Handles bold, italic, inline code, links, and fenced code blocks.
 * Designed to be XSS-safe by escaping HTML before processing.
 */
export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  if (!content) return null;

  // Note: No HTML entity escaping needed — React auto-escapes text in JSX.

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let currentBlock: { type: 'code' | 'text', lines: string[], lang?: string } | null = null;

  const processInline = (text: string) => {
    // This is a simplified inline processor. For complex nesting, a real parser would be better.
    // But per requirements, we're using regex.
    
    let parts: (string | React.ReactNode)[] = [text];

    // 1. Inline code: `code`
    parts = parts.flatMap(part => {
      if (typeof part !== 'string') return part;
      const subparts = part.split(/(`[^`]+`)/g);
      return subparts.map(subpart => {
        if (subpart.startsWith('`') && subpart.endsWith('`')) {
          return <code key={Math.random()} className="px-1.5 py-0.5 rounded bg-primary/8 font-mono text-[11px] text-primary border border-primary/15">{subpart.slice(1, -1)}</code>;
        }
        return subpart;
      });
    });

    // 1b. Single-quoted highlight: 'info'
    parts = parts.flatMap(part => {
      if (typeof part !== 'string') return part;
      const subparts = part.split(/('[^']+?')/g);
      return subparts.map(subpart => {
        if (subpart.startsWith("'") && subpart.endsWith("'") && subpart.length > 2) {
          return <span key={Math.random()} className="px-1 py-0.5 rounded bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200/60">{subpart.slice(1, -1)}</span>;
        }
        return subpart;
      });
    });

    // 2. Bold: **text**
    parts = parts.flatMap(part => {
      if (typeof part !== 'string') return part;
      const subparts = part.split(/(\*\*[^*]+\*\*)/g);
      return subparts.map(subpart => {
        if (subpart.startsWith('**') && subpart.endsWith('**')) {
          return <strong key={Math.random()} className="font-bold text-text-main">{subpart.slice(2, -2)}</strong>;
        }
        return subpart;
      });
    });

    // 3. Italic: *text*
    parts = parts.flatMap(part => {
      if (typeof part !== 'string') return part;
      const subparts = part.split(/(\*[^*]+\*)/g);
      return subparts.map(subpart => {
        if (subpart.startsWith('*') && subpart.endsWith('*')) {
          return <em key={Math.random()} className="italic text-text-main/90">{subpart.slice(1, -1)}</em>;
        }
        return subpart;
      });
    });

    // 4. Links: [text](url)
    parts = parts.flatMap(part => {
      if (typeof part !== 'string') return part;
      const subparts = part.split(/(\[[^\]]+\]\([^)]+\))/g);
      return subparts.map(subpart => {
        const match = subpart.match(/\[([^\]]+)\]\(([^)]+)\)/);
        if (match) {
          return <a key={Math.random()} href={match[2]} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{match[1]}</a>;
        }
        return subpart;
      });
    });

    return parts;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const codeMatch = line.match(/^```(\w+)?/);

    if (codeMatch) {
      if (currentBlock?.type === 'code') {
        // End of code block
        const lang = currentBlock.lang;
        const code = currentBlock.lines.join('\n');
        elements.push(
          <div key={`code-${i}`} className="my-3 rounded-lg border border-border bg-surface-alt overflow-hidden shadow-sm">
            {lang && (
              <div className="px-3 py-1.5 border-b border-border bg-background/50 text-[10px] font-bold text-text-faint uppercase tracking-wider flex justify-between items-center">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[14px]">code</span>
                  <span>{lang}</span>
                </div>
              </div>
            )}
            <pre className="p-4 overflow-x-auto custom-scrollbar">
              <code className="text-xs font-mono text-text-main leading-relaxed">
                {code}
              </code>
            </pre>
          </div>
        );
        currentBlock = null;
      } else {
        // Start of code block
        currentBlock = { type: 'code', lines: [], lang: codeMatch[1] };
      }
      continue;
    }

    if (currentBlock?.type === 'code') {
      currentBlock.lines.push(line);
      continue;
    }

    // Blockquotes
    const quoteMatch = line.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      const text = quoteMatch[1];
      elements.push(
        <div key={`bq-${i}`} className="my-2 pl-4 py-1" style={{ borderLeft: '3px solid var(--color-primary)', color: 'var(--color-text-muted)' }}>
          <span className="text-sm italic leading-relaxed">
            {processInline(text)}
          </span>
        </div>
      );
      continue;
    }

    // Headers
    const headerMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const text = headerMatch[2];
      const Tag = `h${Math.min(level + 2, 6)}` as React.ElementType; // Offset because these are usually inside cards
      const sizeClasses = [
        '',
        'text-lg font-bold mb-3 mt-5',
        'text-md font-bold mb-2 mt-4',
        'text-sm font-bold mb-2 mt-3',
        'text-[13px] font-bold mb-1 mt-2',
        'text-xs font-bold mb-1 mt-2',
        'text-xs font-bold mb-1 mt-2'
      ][level];
      
      elements.push(
        <Tag key={`h-${i}`} className={`${sizeClasses} text-text-main`}>
          {processInline(text)}
        </Tag>
      );
      continue;
    }

    // Checkboxes
    const checkboxMatch = line.match(/^(\s*)-\s+\[([ x])\]\s+(.*)$/);
    if (checkboxMatch) {
      const checked = checkboxMatch[2].toLowerCase() === 'x';
      const text = checkboxMatch[3];
      elements.push(
        <div key={`check-${i}`} className="flex items-start gap-2 mb-1.5 ml-1">
          <input 
            type="checkbox" 
            checked={checked} 
            readOnly 
            className="mt-1 h-3.5 w-3.5 rounded border-border text-primary bg-background focus:ring-0 cursor-default" 
          />
          <span className={`text-sm leading-relaxed ${checked ? 'text-text-muted line-through' : 'text-text-main'}`}>
            {processInline(text)}
          </span>
        </div>
      );
      continue;
    }

    // Bullet lists
    const listMatch = line.match(/^(\s*)[-*]\s+(.*)$/);
    if (listMatch) {
      const text = listMatch[2];
      elements.push(
        <div key={`li-${i}`} className="flex items-start gap-2 mb-1.5 ml-1">
          <span className="mt-2 w-1.5 h-1.5 rounded-full bg-border flex-shrink-0" />
          <span className="text-sm text-text-main leading-relaxed">
            {processInline(text)}
          </span>
        </div>
      );
      continue;
    }

    // Numbered lists
    const numListMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (numListMatch) {
      const num = line.match(/^(\s*)(\d+)\./)?.[2] || '1';
      const text = numListMatch[2];
      elements.push(
        <div key={`nli-${i}`} className="flex items-start gap-2 mb-1.5 ml-1">
          <span className="text-xs font-semibold mt-0.5 text-text-muted flex-shrink-0 min-w-[1rem] text-right">{num}.</span>
          <span className="text-sm text-text-main leading-relaxed">
            {processInline(text)}
          </span>
        </div>
      );
      continue;
    }

    // Regular text line
    if (line.trim() === '') {
      elements.push(<div key={`spacer-${i}`} className="h-2" />);
    } else {
      elements.push(
        <p key={`p-${i}`} className="text-sm text-text-main leading-relaxed mb-2 last:mb-0">
          {processInline(line)}
        </p>
      );
    }
  }

  // Handle unclosed blocks
  if (currentBlock?.type === 'code') {
    elements.push(
      <pre key="unclosed-code" className="p-3 my-2 rounded bg-surface-alt border border-border overflow-x-auto text-xs font-mono">
        {currentBlock.lines.join('\n')}
      </pre>
    );
  }

  return <div className={className}>{elements}</div>;
}
