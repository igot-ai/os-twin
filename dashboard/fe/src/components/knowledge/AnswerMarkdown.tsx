'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Themed Markdown renderer for Knowledge answer blocks.
 *
 * Uses CSS-variable colours so it works in both dark and light themes.
 * Supports GFM (tables, strikethrough, task-lists).
 */

const markdownComponents: Record<string, React.FC<any>> = {
  h1: ({ children, ...p }: any) => (
    <h1 className="text-base font-semibold mt-4 mb-2 leading-snug" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</h1>
  ),
  h2: ({ children, ...p }: any) => (
    <h2 className="text-sm font-semibold mt-3 mb-2 leading-snug" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</h2>
  ),
  h3: ({ children, ...p }: any) => (
    <h3 className="text-[13px] font-semibold mt-3 mb-1.5" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</h3>
  ),
  h4: ({ children, ...p }: any) => (
    <h4 className="text-[12px] font-semibold uppercase tracking-wide mt-3 mb-1" style={{ color: 'var(--color-text-muted)' }} {...p}>{children}</h4>
  ),
  p: ({ children, ...p }: any) => (
    <p className="text-sm leading-relaxed mb-2" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</p>
  ),
  ul: ({ children, ...p }: any) => (
    <ul className="text-sm leading-relaxed mb-2 ml-4 list-disc space-y-0.5" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</ul>
  ),
  ol: ({ children, ...p }: any) => (
    <ol className="text-sm leading-relaxed mb-2 ml-4 list-decimal space-y-0.5" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</ol>
  ),
  li: ({ children, ...p }: any) => (
    <li className="leading-relaxed" {...p}>{children}</li>
  ),
  a: ({ children, href, ...p }: any) => (
    <a className="underline" style={{ color: 'var(--color-primary)' }} href={href} target="_blank" rel="noopener noreferrer" {...p}>{children}</a>
  ),
  strong: ({ children, ...p }: any) => (
    <strong className="font-semibold" style={{ color: 'var(--color-text-main)' }} {...p}>{children}</strong>
  ),
  em: ({ children, ...p }: any) => (
    <em className="italic" {...p}>{children}</em>
  ),
  blockquote: ({ children, ...p }: any) => (
    <blockquote
      className="border-l-2 pl-3 my-2 italic text-[13px]"
      style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
      {...p}
    >
      {children}
    </blockquote>
  ),
  code: ({ inline, className, children, ...p }: any) => {
    if (inline) {
      return (
        <code
          className="px-1 py-px rounded text-[12px] font-mono"
          style={{ background: 'var(--color-background)', color: 'var(--color-primary)' }}
          {...p}
        >
          {children}
        </code>
      );
    }
    return <code className={`${className || ''} font-mono`} {...p}>{children}</code>;
  },
  pre: ({ children, ...p }: any) => (
    <pre
      className="rounded-lg p-3 my-2 overflow-x-auto text-[12px] leading-relaxed font-mono border"
      style={{
        background: 'var(--color-background)',
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-main)',
        scrollbarWidth: 'thin',
      }}
      {...p}
    >
      {children}
    </pre>
  ),
  table: ({ children, ...p }: any) => (
    <div className="overflow-x-auto my-2">
      <table className="text-[13px] border-collapse w-full" {...p}>{children}</table>
    </div>
  ),
  th: ({ children, ...p }: any) => (
    <th
      className="px-2 py-1.5 border text-left text-xs font-semibold"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-background)' }}
      {...p}
    >
      {children}
    </th>
  ),
  td: ({ children, ...p }: any) => (
    <td className="px-2 py-1.5 border text-sm" style={{ borderColor: 'var(--color-border)' }} {...p}>{children}</td>
  ),
  hr: () => <hr className="my-3" style={{ borderColor: 'var(--color-border)' }} />,
};

interface AnswerMarkdownProps {
  /** The raw markdown string to render. */
  content: string;
  /** Extra class names for the wrapper. */
  className?: string;
}

export default function AnswerMarkdown({ content, className = '' }: AnswerMarkdownProps) {
  return (
    <div className={`answer-markdown ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
