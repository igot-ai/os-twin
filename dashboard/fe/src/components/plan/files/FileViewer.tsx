'use client';


import { useFileContent } from '@/hooks/use-files';

interface FileViewerProps {
  planId: string;
  path: string | null;
}

export default function FileViewer({ planId, path }: FileViewerProps) {
  const { content, isLoading, isError } = useFileContent(planId, path);

  if (!path) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background/50 text-text-faint">
        <span className="material-symbols-outlined text-4xl mb-2">draft</span>
        <p className="text-xs font-medium">Select a file to view its content</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col p-4 space-y-4 animate-pulse">
        <div className="h-6 w-1/3 bg-border/20 rounded" />
        <div className="h-full bg-border/10 rounded" />
      </div>
    );
  }

  if (isError || !content) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-danger p-8">
        <span className="material-symbols-outlined text-4xl mb-2">error</span>
        <p className="text-sm font-bold">Failed to load file</p>
        <p className="text-xs mt-1 text-text-muted">{path}</p>
      </div>
    );
  }

  const isImage = content.mime_type.startsWith('image/');
  const isText = content.encoding === 'utf-8';
  const isBase64 = content.encoding === 'base64';

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-surface/30">
      {/* Viewer Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className="material-symbols-outlined text-[18px] text-text-muted shrink-0">
            {isImage ? 'image' : 'description'}
          </span>
          <span className="text-xs font-bold text-text-main truncate" title={path}>
            {path.split('/').pop()}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-border/50 text-text-faint font-mono uppercase">
            {content.mime_type.split('/').pop()}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold text-text-faint">
          <span>{formatSize(content.size)}</span>
          {content.truncated && (
            <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-500">TRUNCATED</span>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {isImage ? (
          <div className="h-full flex items-center justify-center p-8">
            <img
              src={`data:${content.mime_type};base64,${content.content}`}
              alt={path}
              className="max-w-full max-h-full object-contain shadow-2xl rounded border border-border"
            />
          </div>
        ) : isText ? (
          <pre className="p-4 font-mono text-xs leading-relaxed text-text-main whitespace-pre-wrap selection:bg-primary/30">
            {content.content}
          </pre>
        ) : isBase64 ? (
          <div className="p-8 flex flex-col items-center justify-center gap-4">
             <div className="p-6 rounded-2xl bg-surface border border-border flex flex-col items-center gap-3">
               <span className="material-symbols-outlined text-4xl text-text-faint">binary</span>
               <div className="text-center">
                 <p className="text-sm font-bold text-text-main">Binary File</p>
                 <p className="text-xs text-text-muted mt-1">This file cannot be displayed as text.</p>
               </div>
               <button 
                  className="px-4 py-2 bg-primary text-white text-xs font-bold rounded-lg shadow-sm hover:bg-primary-hover transition-colors"
                  onClick={() => {
                    const blob = base64ToBlob(content.content as string, content.mime_type);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = path.split('/').pop() || 'download';
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  Download File
                </button>
             </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-8 text-text-faint italic text-sm">
            Unsupported file encoding or content.
          </div>
        )}
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function base64ToBlob(base64: string, mimeType: string): Blob {
  const byteCharacters = atob(base64);
  const byteArrays = [];
  for (let offset = 0; offset < byteCharacters.length; offset += 512) {
    const slice = byteCharacters.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    byteArrays.push(byteArray);
  }
  return new Blob(byteArrays, { type: mimeType });
}
