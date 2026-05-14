'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { apiGet } from '@/lib/api-client';
import { JobStatusResponse, useKnowledgeTextImport, ImportTextResponse } from '@/hooks/use-knowledge-import';
import { useSettings } from '@/hooks/use-settings';
import { useConfiguredModels } from '@/hooks/use-configured-models';
import { ModelSelect } from '@/components/settings/ModelSelect';

/* ── Inline Folder Browser ─────────────────────────────────────────── */

interface DirEntry {
  name: string;
  path: string;
  has_children: boolean;
}

interface FileEntry {
  name: string;
  path: string;
  size_bytes: number;
}

interface BrowseResult {
  current: string;
  parent: string | null;
  dirs: DirEntry[];
  files: FileEntry[];
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    pdf: 'picture_as_pdf',
    pptx: 'slideshow', ppt: 'slideshow',
    xlsx: 'table_chart', xls: 'table_chart', csv: 'table_chart',
    md: 'article', txt: 'article', doc: 'article', docx: 'article',
    json: 'data_object', html: 'code', xml: 'code',
    mp4: 'movie', mov: 'movie',
  };
  return map[ext] || 'draft';
}

function getFileColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    pdf: '#ef4444', pptx: '#f97316', ppt: '#f97316',
    xlsx: '#22c55e', xls: '#22c55e', csv: '#22c55e',
    md: '#8b5cf6', txt: '#6b7280', doc: '#3b82f6', docx: '#3b82f6',
    json: '#eab308', html: '#06b6d4', xml: '#06b6d4',
    mp4: '#ec4899', mov: '#ec4899',
  };
  return map[ext] || 'var(--color-text-muted)';
}

/**
 * Inline folder browser for navigating server directories.
 * Uses the /fs/browse API to list directories and files.
 */
function FolderBrowserInline({
  selectedPath,
  onSelectPath,
}: {
  selectedPath: string;
  onSelectPath: (path: string) => void;
}) {
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const browse = useCallback(async (path?: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const url = path
        ? '/fs/browse?path=' + encodeURIComponent(path)
        : '/fs/browse';
      const data = await apiGet<BrowseResult>(url);
      setBrowseResult(data);
      onSelectPath(data.current);
    } catch {
      setError('Failed to browse directory');
    } finally {
      setIsLoading(false);
    }
  }, [onSelectPath]);

  useEffect(() => {
    // Start browsing from the selected path if it exists, otherwise root
    browse(selectedPath || undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pathSegments = browseResult?.current.split('/').filter(Boolean) ?? [];
  const fileCount = browseResult?.files?.length ?? 0;
  const dirCount = browseResult?.dirs?.length ?? 0;

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-background)' }}
    >
      {/* Breadcrumb */}
      <div
        className="flex items-center gap-1 px-3 py-2 border-b text-xs font-mono overflow-x-auto whitespace-nowrap"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-faint)' }}
      >
        <span
          className="cursor-pointer shrink-0 hover:opacity-80"
          style={{ color: 'var(--color-primary)' }}
          onClick={() => browse('/')}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>home</span>
        </span>
        {pathSegments.map((part, i) => {
          const accPath = '/' + pathSegments.slice(0, i + 1).join('/');
          const isLast = i === pathSegments.length - 1;
          return (
            <span key={accPath} className="flex items-center gap-0.5">
              <span style={{ color: 'var(--color-text-faint)' }}>/</span>
              {isLast ? (
                <span className="font-medium" style={{ color: 'var(--color-text-main)' }}>{part}</span>
              ) : (
                <span
                  className="cursor-pointer hover:underline"
                  style={{ color: 'var(--color-primary)' }}
                  onClick={() => browse(accPath)}
                >
                  {part}
                </span>
              )}
            </span>
          );
        })}
        {isLoading && (
          <span
            className="ml-auto w-3 h-3 border border-t-transparent rounded-full animate-spin shrink-0"
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }}
          />
        )}
      </div>

      {/* Directory + File listing */}
      <div className="max-h-[280px] overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
        {error && (
          <div className="p-3 text-center text-xs" style={{ color: 'var(--color-danger)' }}>
            {error}
          </div>
        )}

        {!error && browseResult?.parent && (
          <div
            onClick={() => browse(browseResult.parent!)}
            className="flex items-center gap-2 px-3 py-1.5 cursor-pointer font-mono text-xs transition-colors hover:bg-surface-hover"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>folder</span>
            <span>..</span>
          </div>
        )}

        {/* Directories */}
        {!error && browseResult?.dirs.map((d) => (
          <div
            key={d.path}
            onClick={() => browse(d.path)}
            className="flex items-center gap-2 px-3 py-1.5 cursor-pointer font-mono text-xs transition-colors hover:bg-surface-hover"
            style={{ color: 'var(--color-text-main)' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--color-primary)' }}>folder</span>
            <span className="flex-1 truncate">{d.name}</span>
            {d.has_children && (
              <span className="text-text-faint text-[10px] ml-auto">›</span>
            )}
          </div>
        ))}

        {/* Files */}
        {!error && browseResult?.files?.map((f) => (
          <div
            key={f.path}
            className="flex items-center gap-2 px-3 py-1.5 font-mono text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: getFileColor(f.name) }}>
              {getFileIcon(f.name)}
            </span>
            <span className="flex-1 truncate">{f.name}</span>
            <span className="text-[10px] shrink-0" style={{ color: 'var(--color-text-faint)' }}>
              {formatFileSize(f.size_bytes)}
            </span>
          </div>
        ))}

        {/* Empty state */}
        {!error && dirCount === 0 && fileCount === 0 && (
          <div className="p-3 text-center text-xs" style={{ color: 'var(--color-text-faint)' }}>
            No supported files or subdirectories
          </div>
        )}
      </div>

      {/* Footer with counts */}
      {!error && (dirCount > 0 || fileCount > 0) && (
        <div
          className="px-3 py-1.5 border-t text-[10px] flex items-center gap-3"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-faint)' }}
        >
          {dirCount > 0 && <span>{dirCount} folder{dirCount !== 1 ? 's' : ''}</span>}
          {fileCount > 0 && <span>{fileCount} file{fileCount !== 1 ? 's' : ''}</span>}
        </div>
      )}
    </div>
  );
}

/* ── Import Panel Types & Helpers ──────────────────────────────────── */

interface ImportPanelProps {
  selectedNamespace: string | null;
  jobs: JobStatusResponse[];
  activeJob: JobStatusResponse | undefined;
  isLoading: boolean;
  onStartImport: (folderPath: string, options?: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch {
    return isoString;
  }
}

function JobCard({ job, isLatest }: { job: JobStatusResponse; isLatest: boolean }) {
  const progress = job.progress_total > 0
    ? Math.round((job.progress_current / job.progress_total) * 100)
    : 0;

  const stateColors: Record<string, string> = {
    pending: 'var(--color-text-muted)',
    running: 'var(--color-primary)',
    completed: 'var(--color-success)',
    failed: 'var(--color-danger)',
    interrupted: 'var(--color-warning)',
    cancelled: 'var(--color-text-muted)',
  };

  const stateLabels: Record<string, string> = {
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed',
    interrupted: 'Interrupted',
    cancelled: 'Cancelled',
  };

  return (
    <div
      className={`rounded-xl border p-4 ${isLatest ? 'ring-2 ring-primary/20' : ''}`}
      style={{
        background: 'var(--color-surface-hover)',
        borderColor: 'var(--color-border)'
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: stateColors[job.state] }}
          />
          <span
            className="text-xs font-semibold uppercase tracking-wide"
            style={{ color: stateColors[job.state] }}
          >
            {stateLabels[job.state]}
          </span>
        </div>
        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {job.operation}
        </span>
      </div>

      {/* Message */}
      {job.message && (
        <p className="text-sm mb-3" style={{ color: 'var(--color-text-main)' }}>
          {job.message}
        </p>
      )}

      {/* Progress bar (for running jobs) */}
      {job.state === 'running' && job.progress_total > 0 && (
        <div className="mb-3">
          <div className="flex justify-between text-[10px] mb-1">
            <span style={{ color: 'var(--color-text-muted)' }}>Progress</span>
            <span style={{ color: 'var(--color-text-main)' }}>
              {job.progress_current} / {job.progress_total} ({progress}%)
            </span>
          </div>
          <div
            className="h-1.5 rounded-full overflow-hidden"
            style={{ background: 'var(--color-border)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: 'var(--color-primary)' }}
            />
          </div>
        </div>
      )}

      {/* Timestamps */}
      <div className="flex items-center gap-4 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">schedule</span>
          <span>Submitted: {formatTimestamp(job.submitted_at)}</span>
        </div>
        {job.finished_at && (
          <div className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[12px]">check_circle</span>
            <span>Finished: {formatTimestamp(job.finished_at)}</span>
          </div>
        )}
      </div>

      {/* Errors */}
      {job.errors.length > 0 && (
        <div
          className="mt-3 p-2 rounded-lg text-xs"
          style={{ background: 'var(--color-danger-muted)', color: 'var(--color-danger)' }}
        >
          <p className="font-semibold mb-1">Errors ({job.errors.length})</p>
          <ul className="list-disc list-inside space-y-0.5">
            {job.errors.slice(0, 3).map((err, i) => (
              <li key={i} className="truncate">{err}</li>
            ))}
            {job.errors.length > 3 && (
              <li className="italic">+{job.errors.length - 3} more errors</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ImportPanel({
  selectedNamespace,
  jobs,
  activeJob,
  onStartImport,
  onRefresh,
}: ImportPanelProps) {
  const [folderPath, setFolderPath] = useState('');
  const chunkSize = 2048;
  const overlap = 512;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [llmModel, setLlmModel] = useState('');
  const [visionOcr, setVisionOcr] = useState(true);
  const [visionOcrModel, setVisionOcrModel] = useState('gemini-2.0-flash');
  const [showModelSettings, setShowModelSettings] = useState(false);
  const [importMode, setImportMode] = useState<'folder' | 'text'>('folder');
  const [textValue, setTextValue] = useState('');
  const [sourceLabel, setSourceLabel] = useState('inline');
  const [textResult, setTextResult] = useState<ImportTextResponse | null>(null);
  const [textError, setTextError] = useState<string | null>(null);

  const { startImportText, isLoading: isTextLoading } = useKnowledgeTextImport();

  const { settings } = useSettings();
  const configuredLlmModel = settings?.knowledge?.knowledge_llm_model ?? '';
  const { allModels, providers } = useConfiguredModels();
  const chatModels = useMemo(
    () => allModels.filter((m) => !m.id.toLowerCase().includes('embed')),
    [allModels],
  );

  const handleImport = useCallback(async () => {
    if (!folderPath.trim()) return;

    setIsSubmitting(true);
    try {
      const options: Record<string, unknown> = {
        chunk_size: chunkSize,
        overlap,
        vision_ocr: visionOcr,
        vision_ocr_model: visionOcr ? visionOcrModel : '',
      };
      if (llmModel.trim()) {
        options.llm_model = llmModel.trim();
      }
      await onStartImport(folderPath.trim(), options);
      setFolderPath('');
    } finally {
      setIsSubmitting(false);
    }
  }, [folderPath, chunkSize, overlap, visionOcr, visionOcrModel, llmModel, onStartImport]);

  const handleBrowseSelect = useCallback((path: string) => {
    setFolderPath(path);
  }, []);

  const handleBrowseConfirm = useCallback(() => {
    setShowBrowser(false);
  }, []);

  const handleTextImport = useCallback(async () => {
    if (!textValue.trim() || !selectedNamespace) return;
    setTextResult(null);
    setTextError(null);
    try {
      const options: Record<string, unknown> = {
        chunk_size: chunkSize,
        chunk_overlap: overlap,
      };
      if (llmModel.trim()) {
        options.llm_model = llmModel.trim();
      }
      const result = await startImportText(selectedNamespace, {
        text: textValue.trim(),
        source_label: sourceLabel.trim() || 'inline',
        options,
      });
      setTextResult(result);
    } catch (err) {
      setTextError(err instanceof Error ? err.message : String(err));
    }
  }, [textValue, sourceLabel, selectedNamespace, chunkSize, overlap, llmModel, startImportText]);

  if (!selectedNamespace) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <span
            className="material-symbols-outlined text-[48px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            folder_open
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            Select a Namespace
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Choose a namespace from the Namespaces tab to start importing files.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4" style={{ scrollbarWidth: 'thin' }}>
      {/* Import form */}
      <div
        className="rounded-xl border p-4 mb-4"
        style={{
          background: 'var(--color-surface)',
          borderColor: 'var(--color-border)'
        }}
      >
        {/* Mode tabs */}
        <div className="flex gap-1 mb-3 p-0.5 rounded-lg" style={{ background: 'var(--color-background)' }}>
          <button
            onClick={() => setImportMode('folder')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              importMode === 'folder' 
                ? 'bg-primary text-white shadow-sm' 
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">folder_open</span>
            Import Folder
          </button>
          <button
            onClick={() => setImportMode('text')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              importMode === 'text' 
                ? 'bg-primary text-white shadow-sm' 
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <span className="material-symbols-outlined text-[14px]">edit_note</span>
            Paste Text
          </button>
        </div>

        {importMode === 'folder' ? (
        <>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-main)' }}>
          Import Folder
        </h3>

        <div className="space-y-3">
          {/* Folder path input */}
          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Folder Path *
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                placeholder="/absolute/path/to/folder"
                className="flex-1 px-3 py-2 rounded-lg border text-sm"
                style={{
                  background: 'var(--color-background)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-main)'
                }}
              />
              <button
                onClick={() => setShowBrowser(!showBrowser)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  showBrowser
                    ? 'bg-primary/10 border-primary/30 text-primary'
                    : 'border-border text-text-muted hover:bg-surface-hover hover:text-text-main'
                }`}
                aria-label="Browse folders"
                title="Browse server folders"
              >
                <span className="material-symbols-outlined text-[16px]">folder_open</span>
                Browse
              </button>
              <button
                onClick={handleImport}
                disabled={isSubmitting || !folderPath.trim() || !!activeJob}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {isSubmitting ? 'progress_activity' : 'upload'}
                </span>
                {isSubmitting ? 'Importing...' : 'Import'}
              </button>
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
              Enter a path or click Browse to pick a folder on the server
            </p>
          </div>

          {/* Folder Browser */}
          {showBrowser && (
            <div className="space-y-2">
              <FolderBrowserInline
                selectedPath={folderPath}
                onSelectPath={handleBrowseSelect}
              />
              <div className="flex justify-end">
                <button
                  onClick={handleBrowseConfirm}
                  disabled={!folderPath.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-[14px]">check</span>
                  Use this folder
                </button>
              </div>
            </div>
          )}

          {/* Model Settings toggle */}
          <button
            onClick={() => setShowModelSettings(!showModelSettings)}
            className="flex items-center gap-1 text-xs font-medium transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined text-[16px]">
              {showModelSettings ? 'expand_less' : 'expand_more'}
            </span>
            Advanced Settings
          </button>

          {/* Model Settings panel */}
          {showModelSettings && (
            <div
              className="p-4 rounded-lg space-y-5 border"
              style={{ background: 'var(--color-background)', borderColor: 'var(--color-border)' }}
            >
              <div className="space-y-4">
                <h4 className="text-xs font-semibold" style={{ color: 'var(--color-text-main)' }}>Processing Models</h4>
                {/* Entity Extraction Model */}
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    <span className="flex items-center gap-1">
                      <span className="material-symbols-outlined text-[14px]">hub</span>
                      Entity Extraction Model
                    </span>
                  </label>
                  {chatModels.length > 0 ? (
                    <ModelSelect
                      value={llmModel}
                      onChange={setLlmModel}
                      models={chatModels}
                      providers={providers}
                      placeholder={configuredLlmModel || 'Use server default'}
                      showTier={true}
                      showContext={true}
                    />
                  ) : (
                    <input
                      type="text"
                      value={llmModel}
                      onChange={(e) => setLlmModel(e.target.value)}
                      placeholder={configuredLlmModel || 'e.g. gpt-4o, claude-sonnet-4-20250514'}
                      className="w-full px-3 py-1.5 rounded-lg border text-xs font-mono"
                      style={{
                        background: 'var(--color-surface)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-main)'
                      }}
                    />
                  )}
                  <p className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-faint)' }}>
                    {configuredLlmModel
                      ? `Default from settings: ${configuredLlmModel}. Leave blank to use default.`
                      : 'Leave blank to use the default model from settings.'}
                  </p>
                </div>

                {/* Vision OCR */}
                <div className="space-y-2">
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => setVisionOcr(!visionOcr)}
                      className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 mt-0.5"
                      style={{ background: visionOcr ? 'var(--color-primary)' : 'var(--color-border)' }}
                      role="switch"
                      aria-checked={visionOcr}
                    >
                      <span
                        className="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform"
                        style={{ transform: visionOcr ? 'translateX(18px)' : 'translateX(2px)' }}
                      />
                    </button>
                    <div>
                      <label
                        className="block text-xs font-medium"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        <span className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-[14px]">document_scanner</span>
                          Vision OCR
                        </span>
                      </label>
                      <p className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
                        Extract text from PDF/DOCX/PPTX pages via vision model
                      </p>
                    </div>
                  </div>

                  {/* Vision OCR Model */}
                  {visionOcr && (
                    <div className="ml-12 pl-3 border-l-2" style={{ borderColor: 'var(--color-border)' }}>
                      <label
                        className="block text-xs font-medium mb-1"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        <span className="flex items-center gap-1">
                          <span className="material-symbols-outlined text-[14px]">visibility</span>
                          OCR Model
                          <span
                            className="px-1.5 py-0.5 rounded text-[9px] font-semibold"
                            style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
                          >
                            Gemini Flash recommended
                          </span>
                        </span>
                      </label>
                      {chatModels.length > 0 ? (
                        <ModelSelect
                          value={visionOcrModel}
                          onChange={setVisionOcrModel}
                          models={chatModels}
                          providers={providers}
                          placeholder="gemini-2.0-flash"
                          showTier={true}
                          showContext={true}
                        />
                      ) : (
                        <input
                          type="text"
                          value={visionOcrModel}
                          onChange={(e) => setVisionOcrModel(e.target.value)}
                          placeholder="gemini-2.0-flash"
                          className="w-full px-3 py-1.5 rounded-lg border text-xs font-mono"
                          style={{
                            background: 'var(--color-surface)',
                            borderColor: 'var(--color-border)',
                            color: 'var(--color-text-main)'
                          }}
                        />
                      )}
                      <p className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-faint)' }}>
                        Gemini Flash offers the best speed/cost ratio for document OCR. Also supports gpt-4o, claude-sonnet-4-20250514, etc.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Active job warning */}
        {activeJob && importMode === 'folder' && (
          <div
            className="mt-3 p-2 rounded-lg text-xs flex items-center gap-2"
            style={{
              background: 'var(--color-warning-muted)',
              color: 'var(--color-warning)'
            }}
          >
            <span className="material-symbols-outlined text-[16px]">info</span>
            An import job is already running. Wait for it to complete before starting a new one.
          </div>
        )}
        </>
        ) : (
        /* ── Text Import Mode ────────────────────────────────────────── */
        <div className="space-y-3">
          <div>
            <label 
              className="block text-xs font-medium mb-1.5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Source Label
            </label>
            <input
              type="text"
              value={sourceLabel}
              onChange={(e) => setSourceLabel(e.target.value)}
              placeholder="inline"
              className="w-full px-3 py-2 rounded-lg border text-sm"
              style={{ 
                background: 'var(--color-background)', 
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-main)'
              }}
            />
            <p className="text-[10px] mt-1" style={{ color: 'var(--color-text-faint)' }}>
              A label to identify this text source (shown in chunk metadata)
            </p>
          </div>

          <div>
            <label 
              className="block text-xs font-medium mb-1.5"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Text Content *
            </label>
            <textarea
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              placeholder="Paste or type text to ingest directly into the knowledge graph..."
              rows={8}
              className="w-full px-3 py-2 rounded-lg border text-sm resize-y"
              style={{ 
                background: 'var(--color-background)', 
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-main)',
                minHeight: '120px'
              }}
            />
            <div className="flex justify-between mt-1">
              <p className="text-[10px]" style={{ color: 'var(--color-text-faint)' }}>
                {textValue.length.toLocaleString()} / 100,000 characters
              </p>
              {textValue.length > 100_000 && (
                <p className="text-[10px]" style={{ color: 'var(--color-danger)' }}>
                  Text exceeds maximum length
                </p>
              )}
            </div>
          </div>

          {/* Text LLM Model */}
          <button
            onClick={() => setShowModelSettings(!showModelSettings)}
            className="flex items-center gap-1 text-xs font-medium transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <span className="material-symbols-outlined text-[16px]">
              {showModelSettings ? 'expand_less' : 'expand_more'}
            </span>
            Advanced Settings
          </button>

          {showModelSettings && (
            <div 
              className="p-4 rounded-lg space-y-4 border"
              style={{ background: 'var(--color-background)', borderColor: 'var(--color-border)' }}
            >
              <div>
                <label 
                  className="block text-xs font-medium mb-1"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">hub</span>
                    Entity Extraction Model
                  </span>
                </label>
                {chatModels.length > 0 ? (
                  <ModelSelect
                    value={llmModel}
                    onChange={setLlmModel}
                    models={chatModels}
                    providers={providers}
                    placeholder={configuredLlmModel || 'Use server default'}
                    showTier={true}
                    showContext={true}
                  />
                ) : (
                  <input
                    type="text"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder={configuredLlmModel || 'e.g. gpt-4o, claude-sonnet-4-20250514'}
                    className="w-full px-3 py-1.5 rounded-lg border text-xs font-mono"
                    style={{ 
                      background: 'var(--color-surface)', 
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text-main)'
                    }}
                  />
                )}
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-faint)' }}>
                  Leave blank to use the default model from settings.
                </p>
              </div>
            </div>
          )}

          {/* Submit button */}
          <div className="flex justify-end">
            <button
              onClick={handleTextImport}
              disabled={isTextLoading || !textValue.trim() || textValue.length > 100_000}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[16px]">
                {isTextLoading ? 'progress_activity' : 'add_circle'}
              </span>
              {isTextLoading ? 'Ingesting...' : 'Ingest Text'}
            </button>
          </div>

          {/* Inline result */}
          {textResult && (
            <div 
              className="p-3 rounded-lg text-xs flex items-start gap-2"
              style={{ background: 'var(--color-success-muted)', color: 'var(--color-success)' }}
            >
              <span className="material-symbols-outlined text-[16px] mt-0.5">check_circle</span>
              <div>
                <p className="font-semibold">Text ingested successfully</p>
                <p className="mt-1" style={{ color: 'var(--color-text-muted)' }}>
                  {textResult.chunks_added} chunk{textResult.chunks_added !== 1 ? 's' : ''}, {' '}
                  {textResult.entities_added} entit{textResult.entities_added !== 1 ? 'ies' : 'y'}, {' '}
                  {textResult.relations_added} relation{textResult.relations_added !== 1 ? 's' : ''} {' '}
                  in {textResult.elapsed_seconds.toFixed(2)}s
                </p>
              </div>
            </div>
          )}

          {/* Inline error */}
          {textError && (
            <div 
              className="p-3 rounded-lg text-xs flex items-start gap-2"
              style={{ background: 'var(--color-danger-muted)', color: 'var(--color-danger)' }}
            >
              <span className="material-symbols-outlined text-[16px] mt-0.5">error</span>
              <div>
                <p className="font-semibold">Ingestion failed</p>
                <p className="mt-1">{textError}</p>
              </div>
            </div>
          )}
        </div>
        )}
      </div>

      {/* Jobs list */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-main)' }}>
          Import Jobs
        </h3>
        <button
          onClick={onRefresh}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-surface-hover"
          style={{ color: 'var(--color-text-muted)' }}
          aria-label="Refresh jobs"
        >
          <span className="material-symbols-outlined text-[16px]">refresh</span>
          Refresh
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-8">
          <span
            className="material-symbols-outlined text-[32px] mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            history
          </span>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No import jobs yet. Import a folder to see job history.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job, i) => (
            <JobCard key={job.job_id} job={job} isLatest={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
