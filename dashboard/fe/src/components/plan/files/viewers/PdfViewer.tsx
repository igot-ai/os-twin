'use client';

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { base64ToUint8Array } from './utils';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  base64Data: string;
}

export default function PdfViewer({ base64Data }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [pdfUrl, setPdfUrl] = useState<string>('');

  useEffect(() => {
    if (!base64Data) return;
    const byteArray = base64ToUint8Array(base64Data);
    const blob = new Blob([byteArray as BlobPart], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    setPdfUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [base64Data]);

  if (!base64Data) {
    return (
      <div className="p-8 text-center text-danger">
        <span className="material-symbols-outlined text-3xl mb-2 block">error</span>
        <p className="text-sm font-bold">No PDF data</p>
      </div>
    );
  }

  if (!pdfUrl) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-center gap-3 px-4 py-1.5 border-b border-border bg-surface/50 shrink-0">
        <button
          onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
          disabled={pageNumber <= 1}
          className="p-1 rounded hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <span className="material-symbols-outlined text-[16px]">chevron_left</span>
        </button>
        <span className="text-[11px] font-bold text-text-muted">
          {pageNumber} / {numPages || '–'}
        </span>
        <button
          onClick={() => setPageNumber(Math.min(numPages, pageNumber + 1))}
          disabled={pageNumber >= numPages}
          className="p-1 rounded hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <span className="material-symbols-outlined text-[16px]">chevron_right</span>
        </button>
      </div>
      <div className="flex-1 overflow-auto custom-scrollbar p-4 flex justify-center">
        <Document
          file={pdfUrl}
          onLoadSuccess={({ numPages: n }) => setNumPages(n)}
          loading={
            <div className="flex items-center justify-center py-12">
              <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
            </div>
          }
        >
          <Page
            pageNumber={pageNumber}
            renderTextLayer
            renderAnnotationLayer
            className="shadow-lg rounded border border-border"
            width={550}
          />
        </Document>
      </div>
    </div>
  );
}
