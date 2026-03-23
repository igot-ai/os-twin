'use client';

import { useMemo } from 'react';

interface MarkdownPreviewProps {
  content: string;
}

interface FormatValidation {
  hasTitle: boolean;
  hasConfig: boolean;
  hasWorkingDir: boolean;
  epicCount: number;
  hasAcceptanceCriteria: boolean;
  isValid: boolean;
}

function validatePlanFormat(content: string): FormatValidation {
  const hasTitle = /^# Plan:\s*.+/m.test(content);
  const hasConfig = /^## Config/m.test(content);
  const hasWorkingDir = /working_dir:\s*.+/m.test(content);
  const epicMatches = content.match(/^## EPIC-\d+/gm);
  const epicCount = epicMatches?.length || 0;
  const hasAcceptanceCriteria = /Acceptance criteria:|#### Acceptance Criteria/i.test(content);
  const isValid = hasTitle && hasConfig && hasWorkingDir && epicCount > 0 && hasAcceptanceCriteria;

  return { hasTitle, hasConfig, hasWorkingDir, epicCount, hasAcceptanceCriteria, isValid };
}

function renderMarkdown(content: string): string {
  if (!content) return '';

  let html = content
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
  html = html.replace(
    /^## (EPIC-\d+\s*[-—–]\s*.+)$/gm,
    '<h2 class="md-epic"><span class="md-epic-badge">EPIC</span> $1</h2>',
  );
  html = html.replace(
    /^## (Config)$/gm,
    '<h2 class="md-config"><span class="md-config-badge">CONFIG</span> $1</h2>',
  );
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
  html = html.replace(
    /^# Plan:\s*(.+)$/gm,
    '<h1 class="md-title"><span class="md-title-icon">⬡</span> $1</h1>',
  );

  // Config lines (key: value)
  html = html.replace(
    /^(working_dir:\s*)(.+)$/gm,
    '<div class="md-config-line"><span class="md-config-key">$1</span><span class="md-config-val">$2</span></div>',
  );

  // Acceptance criteria header
  html = html.replace(/^(Acceptance criteria:)$/gm, '<div class="md-criteria-header">$1</div>');

  // Bullet lists with checklist style
  html = html.replace(
    /^- (.+)$/gm,
    '<div class="md-bullet"><span class="md-bullet-dot">▸</span> <span>$1</span></div>',
  );

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>');

  // Paragraphs (wrap remaining lines)
  html = html.replace(/^(?!<[h1-6div]|$)(.+)$/gm, '<p class="md-p">$1</p>');

  return html;
}

export default function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const validation = useMemo(() => validatePlanFormat(content), [content]);
  const rendered = useMemo(() => renderMarkdown(content), [content]);

  return (
    <div className="md-preview">
      {/* Format validation badge */}
      <div className="md-validation">
        <span className={`md-badge ${validation.isValid ? 'md-badge-valid' : 'md-badge-invalid'}`}>
          {validation.isValid ? '✓ Valid Plan Format' : '✗ Incomplete Format'}
        </span>
        <div className="md-checks">
          <span className={validation.hasTitle ? 'md-check-ok' : 'md-check-missing'}>
            {validation.hasTitle ? '✓' : '✗'} Title
          </span>
          <span className={validation.hasConfig ? 'md-check-ok' : 'md-check-missing'}>
            {validation.hasConfig ? '✓' : '✗'} Config
          </span>
          <span className={validation.epicCount > 0 ? 'md-check-ok' : 'md-check-missing'}>
            {validation.epicCount > 0 ? '✓' : '✗'} Epics ({validation.epicCount})
          </span>
          <span className={validation.hasAcceptanceCriteria ? 'md-check-ok' : 'md-check-missing'}>
            {validation.hasAcceptanceCriteria ? '✓' : '✗'} Criteria
          </span>
        </div>
      </div>

      {/* Rendered markdown content */}
      <div className="md-body" dangerouslySetInnerHTML={{ __html: rendered }} />
    </div>
  );
}
