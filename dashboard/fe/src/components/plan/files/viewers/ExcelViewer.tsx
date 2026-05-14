'use client';

import { useState, useEffect, useMemo } from 'react';
import * as XLSX from 'xlsx';
import { base64ToUint8Array } from './utils';

interface SheetData {
  name: string;
  headers: string[];
  rows: string[][];
  truncated_rows?: boolean;
  truncated_cols?: boolean;
  total_rows?: number;
}

interface ExcelViewerProps {
  data: string;
  encoding: 'utf-8' | 'base64';
}

// P2-16: Limits to prevent browser DoS from huge spreadsheets
const MAX_ROWS = 1000;
const MAX_COLS = 50;

export default function ExcelViewer({ data, encoding }: ExcelViewerProps) {
  const [sheets, setSheets] = useState<SheetData[]>([]);
  const [activeSheet, setActiveSheet] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      let wb: XLSX.WorkBook;
      if (encoding === 'base64') {
        const byteArray = base64ToUint8Array(data);
        wb = XLSX.read(byteArray, { type: 'array' });
      } else {
        wb = XLSX.read(data, { type: 'string' });
      }
      const parsed: SheetData[] = wb.SheetNames.map((name) => {
        const ws = wb.Sheets[name];
        const json: string[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
        // P2-16: Enforce row and column limits to prevent browser DoS
        const trimmed = json.slice(0, MAX_ROWS).map((row) =>
          (row as string[]).slice(0, MAX_COLS).map(String)
        );
        const headers = trimmed.length > 0 ? trimmed[0] : [];
        const rows = trimmed.slice(1);
        const truncated_rows = json.length > MAX_ROWS;
        const truncated_cols = json.length > 0 && (json[0] as string[]).length > MAX_COLS;
        return { name, headers, rows, truncated_rows, truncated_cols, total_rows: json.length - 1 };
      });
      setSheets(parsed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse spreadsheet');
    }
  }, [data, encoding]);

  const sheet = sheets[activeSheet];

  if (error) {
    return (
      <div className="p-8 text-center text-danger">
        <span className="material-symbols-outlined text-3xl mb-2 block">error</span>
        <p className="text-sm font-bold">Failed to parse spreadsheet</p>
        <p className="text-xs mt-1 text-text-muted">{error}</p>
      </div>
    );
  }

  if (sheets.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="material-symbols-outlined text-primary animate-spin">progress_activity</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {sheets.length > 1 && (
        <div className="flex items-center gap-1 px-4 py-1.5 border-b border-border bg-surface/50 shrink-0 overflow-x-auto">
          {sheets.map((s, i) => (
            <button
              key={s.name}
              onClick={() => setActiveSheet(i)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors whitespace-nowrap ${
                i === activeSheet
                  ? 'bg-primary text-white'
                  : 'text-text-faint hover:text-text-muted hover:bg-surface-hover'
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {sheet && (
          <table className="w-full border-collapse text-[12px]">
            <thead className="sticky top-0 z-10">
              <tr>
                <th className="px-2 py-1.5 border border-border bg-surface text-text-faint font-mono text-[10px] text-center w-8">
                  #
                </th>
                {sheet.headers.map((h, i) => (
                  <th
                    key={i}
                    className="px-3 py-1.5 border border-border bg-surface text-left text-[11px] font-bold text-text-muted whitespace-nowrap"
                  >
                    {h || `Col ${i + 1}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheet.rows.map((row, ri) => (
                <tr key={ri} className="hover:bg-surface-hover/30">
                  <td className="px-2 py-1 border border-border bg-surface/50 text-text-faint/40 font-mono text-[10px] text-center">
                    {ri + 1}
                  </td>
                  {sheet.headers.map((_, ci) => (
                    <td
                      key={ci}
                      className="px-3 py-1 border border-border text-text-main whitespace-nowrap max-w-[300px] truncate"
                    >
                      {row[ci] ?? ''}
                    </td>
                  ))}
                </tr>
              ))}
              {sheet.rows.length === 0 && (
                <tr>
                  <td
                    colSpan={sheet.headers.length + 1}
                    className="px-4 py-8 text-center text-text-faint text-xs"
                  >
                    No data rows
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
      {sheet && (
        <div className="px-4 py-1.5 border-t border-border bg-surface/50 text-[10px] text-text-faint shrink-0">
          {sheet.rows.length} row{sheet.rows.length !== 1 ? 's' : ''} · {sheet.headers.length} column{sheet.headers.length !== 1 ? 's' : ''}
          {(sheet.truncated_rows || sheet.truncated_cols) && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-500">
              TRUNCATED{sheet.truncated_rows ? ` (${sheet.total_rows} total rows, showing ${MAX_ROWS})` : ''}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
