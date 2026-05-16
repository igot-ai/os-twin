'use client';

import { useMemo } from 'react';
import hljs from 'highlight.js/lib/core';
import DOMPurify from 'dompurify';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import python from 'highlight.js/lib/languages/python';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import yaml from 'highlight.js/lib/languages/yaml';
import css from 'highlight.js/lib/languages/css';
import bash from 'highlight.js/lib/languages/bash';
import sql from 'highlight.js/lib/languages/sql';
import markdown from 'highlight.js/lib/languages/markdown';
import go from 'highlight.js/lib/languages/go';
import rust from 'highlight.js/lib/languages/rust';
import java from 'highlight.js/lib/languages/java';
import csharp from 'highlight.js/lib/languages/csharp';
import cpp from 'highlight.js/lib/languages/cpp';
import dockerfile from 'highlight.js/lib/languages/dockerfile';
import shell from 'highlight.js/lib/languages/shell';
import ini from 'highlight.js/lib/languages/ini';
import diff from 'highlight.js/lib/languages/diff';
import plaintext from 'highlight.js/lib/languages/plaintext';

hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('js', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('ts', typescript);
hljs.registerLanguage('python', python);
hljs.registerLanguage('py', python);
hljs.registerLanguage('json', json);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('yaml', yaml);
hljs.registerLanguage('yml', yaml);
hljs.registerLanguage('css', css);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('sh', bash);
hljs.registerLanguage('sql', sql);
hljs.registerLanguage('markdown', markdown);
hljs.registerLanguage('md', markdown);
hljs.registerLanguage('go', go);
hljs.registerLanguage('rust', rust);
hljs.registerLanguage('java', java);
hljs.registerLanguage('csharp', csharp);
hljs.registerLanguage('cs', csharp);
hljs.registerLanguage('cpp', cpp);
hljs.registerLanguage('c', cpp);
hljs.registerLanguage('dockerfile', dockerfile);
hljs.registerLanguage('shell', shell);
hljs.registerLanguage('ini', ini);
hljs.registerLanguage('toml', ini);
hljs.registerLanguage('diff', diff);
hljs.registerLanguage('plaintext', plaintext);
hljs.registerLanguage('text', plaintext);

const EXT_LANG_MAP: Record<string, string> = {
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  py: 'python',
  json: 'json',
  html: 'html',
  htm: 'html',
  xml: 'xml',
  svg: 'xml',
  yml: 'yaml',
  yaml: 'yaml',
  css: 'css',
  scss: 'css',
  sh: 'bash',
  bash: 'bash',
  zsh: 'bash',
  sql: 'sql',
  md: 'markdown',
  go: 'go',
  rs: 'rust',
  java: 'java',
  cs: 'csharp',
  cpp: 'cpp',
  c: 'cpp',
  h: 'cpp',
  toml: 'toml',
  ini: 'ini',
  diff: 'diff',
  patch: 'diff',
  Dockerfile: 'dockerfile',
};

function getLanguageFromPath(path: string): string | undefined {
  const filename = path.split('/').pop() || '';
  if (EXT_LANG_MAP[filename]) return EXT_LANG_MAP[filename];
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return EXT_LANG_MAP[ext];
}

interface CodeViewerProps {
  content: string;
  path: string;
}

export default function CodeViewer({ content, path }: CodeViewerProps) {
  const lang = getLanguageFromPath(path);

  const highlighted = useMemo(() => {
    let raw: string;
    if (!lang || !hljs.getLanguage(lang)) {
      raw = hljs.highlightAuto(content).value;
    } else {
      try {
        raw = hljs.highlight(content, { language: lang }).value;
      } catch {
        // If highlight.js fails, we must still escape the raw content
        // before injecting via dangerouslySetInnerHTML
        raw = content
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');
      }
    }
    // Sanitize to prevent XSS: only allow <span> with class attributes
    // (highlight.js wraps tokens in <span class="hljs-*">)
    return DOMPurify.sanitize(raw, { ALLOWED_TAGS: ['span'], ALLOWED_ATTR: ['class'] });
  }, [content, lang]);

  const lines = content.split('\n');
  const lineCount = lines.length;
  const gutterWidth = String(lineCount).length;

  return (
    <div className="flex text-xs font-mono leading-relaxed">
      <div
        className="select-none text-right pr-3 pl-4 py-4 text-text-faint/40 border-r border-border/30 shrink-0 sticky left-0 bg-surface/30"
        style={{ minWidth: `${gutterWidth + 2}ch` }}
      >
        {lines.map((_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      <pre className="flex-1 p-4 overflow-x-auto">
        <code
          className={`hljs language-${lang || 'plaintext'}`}
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      </pre>
    </div>
  );
}
