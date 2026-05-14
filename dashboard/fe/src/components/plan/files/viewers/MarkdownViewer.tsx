'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

const mdComponents = {
  h1: ({ children, ...p }: any) => (
    <h1 className="text-base font-semibold mt-5 mb-2 leading-snug text-text-main" {...p}>{children}</h1>
  ),
  h2: ({ children, ...p }: any) => (
    <h2 className="text-sm font-semibold mt-4 mb-2 leading-snug text-text-main" {...p}>{children}</h2>
  ),
  h3: ({ children, ...p }: any) => (
    <h3 className="text-[13px] font-semibold mt-3 mb-1.5 text-text-main" {...p}>{children}</h3>
  ),
  p: ({ children, ...p }: any) => (
    <p className="text-[13px] leading-relaxed mb-2 text-text-main" {...p}>{children}</p>
  ),
  ul: ({ children, ...p }: any) => (
    <ul className="text-[13px] leading-relaxed mb-2 ml-4 list-disc space-y-0.5 text-text-main" {...p}>{children}</ul>
  ),
  ol: ({ children, ...p }: any) => (
    <ol className="text-[13px] leading-relaxed mb-2 ml-4 list-decimal space-y-0.5 text-text-main" {...p}>{children}</ol>
  ),
  li: ({ children, ...p }: any) => (
    <li className="leading-relaxed" {...p}>{children}</li>
  ),
  a: ({ children, href, ...p }: any) => {
    // P2-14: Comprehensive dangerous protocol check.
    // Strips whitespace/control chars before checking to prevent bypasses
    // like "java\tscript:" or "java\nscript:" which browsers may normalize.
    const isSafe = href && (() => {
      // Strip all ASCII whitespace and control characters for protocol check
      const normalized = href.replace(/[\x00-\x20\x7f]/g, '').toLowerCase();
      const dangerousProtocols = ['javascript:', 'data:', 'vbscript:', 'file:'];
      return !dangerousProtocols.some(proto => normalized.startsWith(proto));
    })();
    return (
      <a className="underline text-primary" href={isSafe ? href : undefined} target="_blank" rel="noopener noreferrer" {...p}>{children}</a>
    );
  },
  strong: ({ children, ...p }: any) => (
    <strong className="font-semibold text-text-main" {...p}>{children}</strong>
  ),
  em: ({ children, ...p }: any) => (
    <em className="italic" {...p}>{children}</em>
  ),
  blockquote: ({ children, ...p }: any) => (
    <blockquote className="border-l-2 pl-3 my-2 italic text-[12px] text-text-muted border-border" {...p}>{children}</blockquote>
  ),
  code: ({ inline, className, children, ...p }: any) => {
    if (inline) {
      return (
        <code className="px-1 py-px rounded text-[12px] font-mono bg-background text-primary" {...p}>{children}</code>
      );
    }
    return <code className={`${className || ''} font-mono`} {...p}>{children}</code>;
  },
  pre: ({ children, ...p }: any) => (
    <pre className="rounded-lg p-3 my-2 overflow-x-auto text-[12px] leading-relaxed font-mono border bg-background border-border text-text-main" {...p}>{children}</pre>
  ),
  table: ({ children, ...p }: any) => (
    <div className="overflow-x-auto my-2">
      <table className="text-[13px] border-collapse w-full" {...p}>{children}</table>
    </div>
  ),
  th: ({ children, ...p }: any) => (
    <th className="px-2 py-1.5 border text-left text-xs font-semibold bg-background border-border" {...p}>{children}</th>
  ),
  td: ({ children, ...p }: any) => (
    <td className="px-2 py-1.5 border text-sm border-border" {...p}>{children}</td>
  ),
  hr: () => <hr className="my-3 border-border" />,
};

interface MarkdownViewerProps {
  content: string;
}

export default function MarkdownViewer({ content }: MarkdownViewerProps) {
  return (
    <div className="p-4">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} components={mdComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
