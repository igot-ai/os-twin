'use client';

import React, { useState, useCallback, useRef } from 'react';
import useSWR from 'swr';
import { usePlanContext } from './PlanWorkspace';
import { PlanAsset } from '@/types';
import { useAssets } from '@/hooks/use-assets';
import { apiPost } from '@/lib/api-client';

const ASSET_TYPES = [
  'design-mockup', 'api-spec', 'test-data', 'reference-doc', 'config', 'media', 'other',
];

function formatBytes(bytes = 0): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getTypeIcon(type?: string): string {
  switch (type) {
    case 'design-mockup': return 'palette';
    case 'api-spec': return 'api';
    case 'test-data': return 'science';
    case 'reference-doc': return 'description';
    case 'config': return 'settings';
    case 'media': return 'movie';
    default: return 'attachment';
  }
}

function isPreviewable(mime: string): boolean {
  return mime.startsWith('image/') || mime.startsWith('text/');
}

export default function AssetPanel() {
  const { planId, epics } = usePlanContext();
  const {
    assets,
    isLoading,
    uploading,
    uploadAssets,
    bindAsset,
    unbindAsset,
    updateAssetMeta,
  } = useAssets(planId);

  const [isDragging, setIsDragging] = useState<string | null>(null); // null, 'plan', or epic_ref
  const [generating, setGenerating] = useState(false);
  const [generatingStatus, setGeneratingStatus] = useState<string | null>(null);
  const [editingAsset, setEditingAsset] = useState<string | null>(null);
  const [previewAsset, setPreviewAsset] = useState<PlanAsset | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Group assets by epic
  const planLevel: PlanAsset[] = [];
  const byEpic: Record<string, PlanAsset[]> = {};
  for (const asset of assets) {
    const epicsArr = asset.bound_epics || [];
    if (epicsArr.length === 0) {
      planLevel.push(asset);
    } else {
      for (const e of epicsArr) {
        if (!byEpic[e]) byEpic[e] = [];
        byEpic[e].push(asset);
      }
    }
  }

  // Upload handler wrapper for error handling
  const handleUpload = useCallback(async (files: FileList | File[], epicRef?: string) => {
    try {
      await uploadAssets(files, epicRef);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      alert(`Upload failed: ${message}`);
    }
  }, [uploadAssets]);

  // Drag and drop
  const handleDragOver = useCallback((e: React.DragEvent, ref: string = 'plan') => {
    e.preventDefault();
    setIsDragging(ref);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(null);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, ref: string = 'plan') => {
    e.preventDefault();
    setIsDragging(null);
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files, ref === 'plan' ? undefined : ref);
    }
  }, [handleUpload]);

  // Bind/Unbind
  const handleBind = useCallback(async (filename: string, epicRef: string) => {
    await bindAsset(filename, epicRef);
  }, [bindAsset]);

  const handleUnbind = useCallback(async (filename: string, epicRef: string) => {
    await unbindAsset(filename, epicRef);
  }, [unbindAsset]);

  // Update metadata
  const handleUpdateMeta = useCallback(async (filename: string, updates: Partial<PlanAsset>) => {
    await updateAssetMeta(filename, updates);
    setEditingAsset(null);
  }, [updateAssetMeta]);

  // Generate plan from assets
  const handleGeneratePlan = useCallback(async () => {
    if (assets.length === 0) return;
    
    setGenerating(true);
    setGeneratingStatus('🚀 Starting plan generation...');
    
    try {
      // Show progress message
      setGeneratingStatus('📚 Analyzing uploaded assets...');
      
      // Small delay to show the message
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setGeneratingStatus('🤖 AI is generating your plan...');
      
      const result: any = await apiPost(`/plans/${planId}/generate-from-assets`, {});
      
      if (result.status === 'generated') {
        setGeneratingStatus('✅ Plan generated! Refreshing...');
        
        // Brief pause to show success message
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Reload the page to show the new plan content
        window.location.reload();
      } else {
        setGeneratingStatus(null);
        alert('Plan generation completed with unexpected response');
      }
    } catch (error: unknown) {
      console.error('Failed to generate plan:', error);
      setGeneratingStatus(null);
      const message = error instanceof Error ? error.message : 'Unknown error';
      alert(`Failed to generate plan: ${message}`);
    } finally {
      setGenerating(false);
    }
  }, [planId, assets.length]);

  function TextPreview({ url }: { url: string }) {
  const { data, error, isLoading } = useSWR(url, (u) => fetch(u).then(r => r.text()));

  if (isLoading) return <div className="p-8 text-center animate-pulse text-text-faint text-xs">Loading text preview...</div>;
  if (error) return <div className="p-8 text-center text-danger text-xs">Failed to load text preview.</div>;

  return (
    <pre className="p-4 bg-background border border-border rounded-lg overflow-auto max-h-[60vh] text-[10px] text-text-main font-mono whitespace-pre-wrap">
      {data}
    </pre>
  );
}

// Asset card
  const AssetCard = ({ asset, showBinding = false }: { asset: PlanAsset; showBinding?: boolean }) => {
    const isEditing = editingAsset === asset.filename;
    const [editType, setEditType] = useState(asset.asset_type || 'unspecified');
    const [editDesc, setEditDesc] = useState(asset.description || '');
    const [editTags, setEditTags] = useState((asset.tags || []).join(', '));

    return (
      <div className="border border-border rounded-lg p-3 bg-surface hover:bg-surface-hover transition-all group">
        <div className="flex items-start gap-3">
          {/* Type icon */}
          <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[16px] text-primary">
              {getTypeIcon(asset.asset_type)}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            {/* Filename */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-text-main truncate">
                {asset.original_name}
              </span>
              {asset.asset_type && asset.asset_type !== 'unspecified' && (
                <span className="text-[10px] px-1.5 py-0.5 bg-primary/10 text-primary rounded font-medium">
                  {asset.asset_type}
                </span>
              )}
            </div>

            {/* Tags */}
            {(asset.tags || []).length > 0 && (
              <div className="flex gap-1 mt-1 flex-wrap">
                {(asset.tags || []).map(tag => (
                  <span key={tag} className="text-[9px] px-1.5 py-0.5 bg-border/40 text-text-muted rounded">
                    #{tag}
                  </span>
                ))}
              </div>
            )}

            {/* Meta */}
            <div className="text-[10px] text-text-muted mt-1 flex gap-2">
              <span>{asset.mime_type}</span>
              <span>{formatBytes(asset.size_bytes)}</span>
            </div>

            {/* Description */}
            {asset.description && !isEditing && (
              <p className="text-[11px] text-text-muted mt-1 line-clamp-2">{asset.description}</p>
            )}

            {/* Binding badges */}
            {showBinding && (asset.bound_epics || []).length > 0 && (
              <div className="flex gap-1 mt-1.5 flex-wrap">
                {(asset.bound_epics || []).map(e => (
                  <span
                    key={e}
                    className="text-[9px] px-1.5 py-0.5 bg-accent/10 text-accent rounded-full cursor-pointer hover:bg-danger/10 hover:text-danger transition-colors"
                    onClick={() => handleUnbind(asset.filename, e)}
                    title={`Click to unbind from ${e}`}
                  >
                    {e} x
                  </span>
                ))}
              </div>
            )}

            {/* Inline editor */}
            {isEditing && (
              <div className="mt-2 space-y-2">
                <select
                  value={editType}
                  onChange={e => setEditType(e.target.value)}
                  className="w-full text-xs border border-border rounded px-2 py-1 bg-background text-text-main"
                >
                  <option value="unspecified">Unspecified</option>
                  {ASSET_TYPES.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                <input
                  type="text"
                  value={editDesc}
                  onChange={e => setEditDesc(e.target.value)}
                  placeholder="Description..."
                  className="w-full text-xs border border-border rounded px-2 py-1 bg-background text-text-main"
                />
                <input
                  type="text"
                  value={editTags}
                  onChange={e => setEditTags(e.target.value)}
                  placeholder="Tags (comma separated)..."
                  className="w-full text-xs border border-border rounded px-2 py-1 bg-background text-text-main"
                />
                <div className="flex gap-1">
                  <button
                    onClick={() => handleUpdateMeta(asset.filename, { 
                      asset_type: editType, 
                      description: editDesc,
                      tags: editTags.split(',').map(t => t.trim()).filter(t => t)
                    })}
                    className="text-[10px] px-2 py-1 bg-primary text-white rounded hover:bg-primary/80"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingAsset(null)}
                    className="text-[10px] px-2 py-1 border border-border rounded hover:bg-surface-hover text-text-muted"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            {isPreviewable(asset.mime_type) && (
              <button
                onClick={() => setPreviewAsset(asset)}
                className="p-1 rounded hover:bg-primary/10 text-text-faint hover:text-primary"
                title="Preview"
              >
                <span className="material-symbols-outlined text-[14px]">visibility</span>
              </button>
            )}
            <button
              onClick={() => setEditingAsset(isEditing ? null : asset.filename)}
              className="p-1 rounded hover:bg-primary/10 text-text-faint hover:text-primary"
              title="Edit metadata"
            >
              <span className="material-symbols-outlined text-[14px]">edit</span>
            </button>
            {asset.path && (
              <a
                href={`/api/plans/${planId}/assets/${encodeURIComponent(asset.filename)}/download`}
                className="p-1 rounded hover:bg-primary/10 text-text-faint hover:text-primary"
                title="Download"
              >
                <span className="material-symbols-outlined text-[14px]">download</span>
              </a>
            )}
          </div>
        </div>

        {/* Bind to epic dropdown */}
        {showBinding && (
          <div className="mt-2 pt-2 border-t border-border/50">
            <select
              defaultValue=""
              onChange={e => {
                if (e.target.value) handleBind(asset.filename, e.target.value);
                e.target.value = '';
              }}
              className="text-[10px] border border-border rounded px-1.5 py-0.5 bg-background text-text-muted w-full"
            >
              <option value="">Bind to epic...</option>
              {(epics || []).map(ep => (
                <option key={ep.epic_ref} value={ep.epic_ref}>
                  {ep.epic_ref} — {ep.title}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-20 bg-border/20 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0 bg-surface-hover/30">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-primary">attach_file</span>
          <span className="text-xs font-bold text-text-main uppercase tracking-widest">Assets</span>
          <span className="text-[10px] px-1.5 py-0.5 bg-border/30 rounded-full text-text-muted font-medium">
            {assets.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {assets.length > 0 && (
            <button
              onClick={handleGeneratePlan}
              disabled={generating || uploading}
              className="text-[11px] px-3 py-1.5 bg-success/10 text-success border border-success/30 rounded-md hover:bg-success/20 transition-colors disabled:opacity-50 flex items-center gap-1"
              title="Generate a plan based on uploaded assets using AI"
            >
              <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
              {generating ? 'Generating...' : 'Generate Plan'}
            </button>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || generating}
            className="text-[11px] px-3 py-1.5 bg-primary text-white rounded-md hover:bg-primary/80 transition-colors disabled:opacity-50 flex items-center gap-1"
            title="Upload individual files or ZIP archives (ZIPs extract automatically for bulk uploads)"
          >
            <span className="material-symbols-outlined text-[14px]">upload</span>
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => {
            if (e.target.files) handleUpload(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      {/* Generation status banner */}
      {generatingStatus && (
        <div className="p-3 bg-primary/5 border-b border-primary/20 flex items-center gap-2 shrink-0 animate-pulse">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-primary font-medium">{generatingStatus}</span>
        </div>
      )}

      {/* Drop zone + content */}
      <div
        className={`flex-1 overflow-y-auto custom-scrollbar transition-colors ${
          isDragging === 'plan' ? 'bg-primary/5' : ''
        }`}
        onDragOver={(e) => handleDragOver(e, 'plan')}
        onDragLeave={handleDragLeave}
        onDrop={(e) => handleDrop(e, 'plan')}
      >
        <div className="p-4 min-h-full">
          {assets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[400px] text-center text-text-muted border-2 border-dashed border-border rounded-xl mt-4">
              <span className="material-symbols-outlined text-[48px] text-text-faint mb-3">cloud_upload</span>
              <p className="text-sm font-medium">No assets yet</p>
              <p className="text-xs mt-1">
                Drag and drop files here, or click Upload to add assets to this plan.
              </p>
              <p className="text-xs mt-2 text-primary">
                💡 Tip: Upload a ZIP file to batch-upload 50+ images at once!
              </p>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Help hint for bulk uploads */}
              <div className="bg-primary/5 border border-primary/20 rounded-md p-2 text-xs text-text-muted flex items-center gap-2">
                <span className="material-symbols-outlined text-[14px] text-primary">info</span>
                <span>
                  <strong>Need to upload 50+ images?</strong> Upload them as a ZIP file — they&apos;ll extract automatically!
                </span>
              </div>
              
              {/* Plan-level assets */}
              <section 
                className={`p-3 rounded-xl border-2 transition-all ${
                  isDragging === 'plan' ? 'border-primary bg-primary/5 shadow-inner' : 'border-transparent'
                }`}
                onDragOver={(e) => { e.stopPropagation(); handleDragOver(e, 'plan'); }}
                onDrop={(e) => { e.stopPropagation(); handleDrop(e, 'plan'); }}
              >
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[14px]">public</span>
                  Plan-level Assets
                  <span className="ml-auto text-[9px] font-medium bg-border/40 px-1.5 py-0.5 rounded-full">
                    {planLevel.length} files
                  </span>
                </h3>
                <div className="space-y-2">
                  {planLevel.length === 0 ? (
                    <div className="py-8 text-center border border-dashed border-border rounded-lg text-[10px] text-text-faint italic">
                      No plan-level assets. Drag files here to upload.
                    </div>
                  ) : (
                    planLevel.map(a => (
                      <AssetCard key={a.filename} asset={a} showBinding />
                    ))
                  )}
                </div>
              </section>

              {/* Per-epic assets */}
              {epics?.map(epic => {
                const epicAssets = byEpic[epic.epic_ref] || [];
                return (
                  <section 
                    key={epic.epic_ref}
                    className={`p-3 rounded-xl border-2 transition-all ${
                      isDragging === epic.epic_ref ? 'border-primary bg-primary/5 shadow-inner' : 'border-transparent'
                    }`}
                    onDragOver={(e) => { e.stopPropagation(); handleDragOver(e, epic.epic_ref); }}
                    onDrop={(e) => { e.stopPropagation(); handleDrop(e, epic.epic_ref); }}
                  >
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-muted mb-3 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[14px]">task</span>
                      {epic.epic_ref} — {epic.title}
                      <span className="ml-auto text-[9px] font-medium bg-border/40 px-1.5 py-0.5 rounded-full">
                        {epicAssets.length} files
                      </span>
                    </h3>
                    <div className="space-y-2">
                      {epicAssets.length === 0 ? (
                        <div className="py-4 text-center border border-dashed border-border rounded-lg text-[10px] text-text-faint italic">
                          No assets bound to this epic. Drag files here to bind.
                        </div>
                      ) : (
                        epicAssets.map(a => (
                          <AssetCard key={a.filename} asset={a} />
                        ))
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Preview modal */}
      {previewAsset && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-8" onClick={() => setPreviewAsset(null)}>
          <div className="bg-surface rounded-xl shadow-2xl max-w-3xl max-h-[80vh] overflow-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-text-main">{previewAsset.original_name}</h3>
              <button onClick={() => setPreviewAsset(null)} className="text-text-muted hover:text-text-main">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            {previewAsset.mime_type.startsWith('image/') && previewAsset.path && (
              <img
                src={`/api/plans/${planId}/assets/${encodeURIComponent(previewAsset.filename)}/download`}
                alt={previewAsset.original_name}
                className="max-w-full rounded-lg mx-auto"
              />
            )}
            {previewAsset.mime_type.startsWith('text/') && (
              <TextPreview url={`/api/plans/${planId}/assets/${encodeURIComponent(previewAsset.filename)}/download`} />
            )}
            {previewAsset.mime_type === 'application/pdf' && (
              <div className="flex flex-col items-center gap-4 py-12">
                <span className="material-symbols-outlined text-[64px] text-text-faint">picture_as_pdf</span>
                <p className="text-sm text-text-muted">PDF preview not supported inline.</p>
                <a 
                  href={`/api/plans/${planId}/assets/${encodeURIComponent(previewAsset.filename)}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-primary text-white rounded-lg text-xs font-bold"
                >
                  Open PDF in New Tab
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
