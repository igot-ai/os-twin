'use client';

import { useMemo } from 'react';

interface MarkdownContentProps {
  content: string;
}

/**
 * A simple regex-based markdown renderer for skills and plan descriptions.
 */
function renderMarkdown(content: string): string {
  if (!content) return '';

  let html = content
    // Escape HTML (simple)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Headers (multi-line)
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>');

  // Code blocks
  html = html.replace(/```(.*?)\n([\s\S]*?)```/gm, '<pre class="md-pre-block"><code>$2</code></pre>');

  // Bullet lists
  html = html.replace(/^- (.+)$/gm, '<div class="md-li"><span>•</span> <span>$1</span></div>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr class="md-hr" />');

  // Paragraphs
  html = html.replace(/^(?!<[h1-6div|pre|hr])(.+)$/gm, '<p class="md-p">$1</p>');

  return html;
}

export default function MarkdownContent({ content }: MarkdownContentProps) {
  const rendered = useMemo(() => renderMarkdown(content), [content]);

  return (
    <div 
      className="markdown-body" 
      dangerouslySetInnerHTML={{ __html: rendered }} 
    />
  );
}
