'use client';

import { useState, useEffect } from 'react';
import mammoth from 'mammoth';
import DOMPurify from 'dompurify';
import { base64ToUint8Array } from './utils';

interface DocxViewerProps {
  base64Data: string;
}

export default function DocxViewer({ base64Data }: DocxViewerProps) {
  const [html, setHtml] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!base64Data) return;
    const byteArray = base64ToUint8Array(base64Data);
    mammoth
      .convertToHtml({ arrayBuffer: byteArray.buffer as ArrayBuffer })
      .then((result) => {
        // P2-11: Restrict DOMPurify to only allow safe HTML tags.
        // Prevents external resource loading (<img>, <link>), phishing links,
        // CSS exfiltration (<style>), and phishing forms (<form>).
        setHtml(DOMPurify.sanitize(result.value, {
          ALLOWED_TAGS: [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'br', 'hr',
            'ul', 'ol', 'li',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'strong', 'em', 'b', 'i', 'u', 'sub', 'sup',
            'blockquote', 'pre', 'code',
            'span', 'div',
          ],
          ALLOWED_ATTR: ['class', 'style'],
          // Strip all URLs to prevent tracking pixels and external resource loading
          FORBID_TAGS: ['img', 'form', 'input', 'button', 'style', 'link', 'script', 'object', 'embed', 'iframe'],
          FORBID_ATTR: ['src', 'href', 'action', 'formaction', 'xlink:href'],
        }));
        if (result.messages.length > 0) {
          console.warn('DocxViewer mammoth warnings:', result.messages);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to parse DOCX');
      });
  }, [base64Data]);

  if (!base64Data) {
    return (
      <div className="p-8 text-center text-danger">
        <span className="material-symbols-outlined text-3xl mb-2 block">error</span>
        <p className="text-sm font-bold">No document data</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-danger">
        <span className="material-symbols-outlined text-3xl mb-2 block">error</span>
        <p className="text-sm font-bold">Failed to parse DOCX</p>
        <p className="text-xs mt-1 text-text-muted">{error}</p>
      </div>
    );
  }

  if (!html) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  return (
    <div
      className="p-6 prose-sm text-text-main max-w-none [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-5 [&_h1]:mb-2 [&_h1]:text-text-main [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:text-text-main [&_h3]:text-[13px] [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:text-text-main [&_p]:text-[13px] [&_p]:leading-relaxed [&_p]:mb-2 [&_p]:text-text-main [&_ul]:ml-4 [&_ul]:list-disc [&_ol]:ml-4 [&_ol]:list-decimal [&_table]:w-full [&_table]:border-collapse [&_th]:px-2 [&_th]:py-1.5 [&_th]:border [&_th]:border-border [&_th]:text-left [&_th]:text-xs [&_th]:font-semibold [&_th]:bg-background [&_td]:px-2 [&_td]:py-1.5 [&_td]:border [&_td]:border-border [&_td]:text-sm"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
