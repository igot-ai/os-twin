'use client';

import React from 'react';

function renderLine(line: string, index: number) {
  if (line.startsWith('### ')) {
    return (
      <h3 key={index} className="text-base font-bold text-text-main mt-4 mb-1">
        {line.slice(4)}
      </h3>
    );
  }
  if (line.startsWith('## ')) {
    return (
      <h2 key={index} className="text-lg font-bold text-text-main mt-5 mb-1.5 border-b border-border pb-1">
        {line.slice(3)}
      </h2>
    );
  }
  if (line.startsWith('# ')) {
    return (
      <h1 key={index} className="text-xl font-black text-text-main mt-6 mb-2">
        {line.slice(2)}
      </h1>
    );
  }
  if (line.startsWith('- ') || line.startsWith('* ')) {
    return (
      <li key={index} className="text-sm text-text-main leading-relaxed ml-4 list-disc">
        {line.slice(2)}
      </li>
    );
  }
  if (line.trim() === '') {
    return <div key={index} className="h-2" />;
  }
  return (
    <p key={index} className="text-sm text-text-main leading-relaxed">
      {line}
    </p>
  );
}

interface MarkdownPreviewProps {
  content: string;
}

export function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const lines = content.split('\n');

  return (
    <div className="p-6 overflow-y-auto h-full custom-scrollbar">
      {content.trim() ? (
        lines.map((line, i) => renderLine(line, i))
      ) : (
        <div className="flex flex-col items-center justify-center h-full text-center">
          <span className="material-symbols-outlined text-4xl text-text-faint mb-3">visibility</span>
          <p className="text-sm text-text-muted">Nothing to preview yet.</p>
        </div>
      )}
    </div>
  );
}
