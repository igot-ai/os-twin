import React, { useState, useRef, useLayoutEffect, useMemo, forwardRef } from 'react';
import { processImages, MAX_IMAGES, type ProcessedImage } from '@/lib/image-utils';
import type { ImageAttachment } from '@/types';

export interface AttachedTemplate {
  id: string;
  name: string;
}

interface CommandPromptProps {
  onSubmit: (prompt: string, images?: ImageAttachment[]) => void;
  isConversationActive?: boolean;
  value?: string;
  onChange?: (val: string) => void;
  isLoading?: boolean;
  /** Attached template shown as a chip inside the prompt area */
  attachedTemplate?: AttachedTemplate | null;
  onRemoveTemplate?: () => void;
}

function useMergedRef<T>(...refs: Array<React.Ref<T> | null | undefined>) {
  return useMemo(
    () => (node: T | null) => {
      refs.forEach(r => {
        if (!r) return;
        if (typeof r === 'function') r(node);
        else (r as React.MutableRefObject<T | null>).current = node;
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    refs,
  );
}

export const CommandPrompt = forwardRef<HTMLTextAreaElement, CommandPromptProps>(({ onSubmit, isConversationActive = false, value, onChange, isLoading = false, attachedTemplate, onRemoveTemplate }, ref) => {
  const [internalPrompt, setInternalPrompt] = useState('');
  const [pendingImages, setPendingImages] = useState<ProcessedImage[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const innerTextareaRef = useRef<HTMLTextAreaElement>(null);

  const mergedRef = useMergedRef<HTMLTextAreaElement>(ref, innerTextareaRef);

  const isControlled = value !== undefined && onChange !== undefined;
  const prompt = isControlled ? value : internalPrompt;
  const setPrompt = isControlled ? onChange : setInternalPrompt;

  const addImages = async (files: FileList | File[]) => {
    const remaining = MAX_IMAGES - pendingImages.length;
    if (remaining <= 0) {
      setImageError(`Maximum ${MAX_IMAGES} images allowed.`);
      return;
    }
    const sliced = Array.from(files).slice(0, remaining);
    const { images, errors } = await processImages(sliced);
    if (errors.length > 0) setImageError(errors.join(' '));
    else setImageError(null);
    if (images.length > 0) setPendingImages(prev => [...prev, ...images]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addImages(e.target.files);
      e.target.value = '';
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault();
      addImages(imageFiles);
    }
  };

  const doSubmit = () => {
    const hasText = prompt.trim().length > 0;
    const hasImages = pendingImages.length > 0;
    const hasTemplate = !!attachedTemplate;
    if (!hasText && !hasImages && !hasTemplate) return;

    const images: ImageAttachment[] | undefined = hasImages
      ? pendingImages.map(img => ({ url: img.url, name: img.name, type: img.type }))
      : undefined;

    onSubmit(prompt, images);
    if (!isControlled) setInternalPrompt('');
    setPendingImages([]);
    setImageError(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd+Enter submits. Plain Enter inserts a newline so the user can
    // safely edit multi-line templates (e.g. prompt templates with {{ }}
    // placeholders) without accidentally submitting a half-filled template.
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      doSubmit();
    }
  };

  const removeImage = (index: number) => {
    setPendingImages(prev => prev.filter((_, i) => i !== index));
    setImageError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSubmit();
  };

  useLayoutEffect(() => {
    const el = innerTextareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, window.innerHeight * 0.4) + 'px';
  }, [prompt]);

  return (
    <div className={isConversationActive ? 'w-full max-w-4xl mx-auto' : 'w-full max-w-2xl mx-auto mt-8'}>
      {/* Template chip — isolated above the input box */}
      {attachedTemplate && (
        <div className="flex items-center gap-2 mb-2 px-1 animate-in fade-in slide-in-from-top-2 duration-200">
          <span
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>description</span>
            @{attachedTemplate.name}
            <button
              type="button"
              onClick={onRemoveTemplate}
              className="ml-1 rounded-full hover:bg-[var(--color-primary)]/20 p-0.5 transition-colors"
              aria-label="Remove template"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
            </button>
          </span>
        </div>
      )}

      {/* Image preview strip */}
      {pendingImages.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 px-4">
          {pendingImages.map((img, i) => (
            <div key={i} className="relative group">
              <img
                src={img.url}
                alt={img.name}
                className="w-14 h-14 object-cover rounded-lg"
                style={{ border: '1px solid var(--color-border)' }}
              />
              <button
                onClick={() => removeImage(i)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: 'var(--color-danger, #ef4444)' }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
              </button>
            </div>
          ))}
        </div>
      )}
      {imageError && (
        <div className="text-xs px-4 mb-1" style={{ color: 'var(--color-danger, #ef4444)' }}>{imageError}</div>
      )}

      <form
        onSubmit={handleSubmit}
        className="relative flex items-center bg-surface/80 backdrop-blur-[12px] border border-border rounded-2xl shadow-card transition-all duration-300 focus-within:ring-4 focus-within:ring-primary-muted focus-within:border-primary hover:border-primary-light"
      >
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />

        <button
          type="button"
          className="p-3 ml-2 text-text-muted hover:text-primary transition-colors active:scale-95 disabled:opacity-30 flex-shrink-0"
          aria-label="Add image"
          disabled={isLoading || pendingImages.length >= MAX_IMAGES}
          onClick={() => fileInputRef.current?.click()}
        >
          <span className="material-symbols-outlined text-xl">add_photo_alternate</span>
        </button>

        <textarea
          ref={mergedRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onPaste={handlePaste}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={attachedTemplate ? "Add details about your project..." : "What do you want to build?"}
          aria-label="Prompt"
          aria-describedby="command-prompt-hint"
          rows={1}
          className="flex-1 bg-transparent border-none py-4 px-2 text-[16px] font-[var(--font-display)] text-[var(--color-text-main)] outline-none placeholder:text-[var(--color-text-faint)] transition-all disabled:opacity-50 resize-none"
          style={{ maxHeight: '40vh' }}
        />

        <div className="flex items-center pr-3 flex-shrink-0">
          <button
            type="submit"
            disabled={(!prompt.trim() && pendingImages.length === 0 && !attachedTemplate) || isLoading}
            className="p-2 bg-primary text-white rounded-full hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 active:scale-95 flex items-center justify-center min-w-[36px] min-h-[36px]"
            aria-label="Send prompt (Ctrl or Cmd + Enter)"
          >
            {isLoading ? (
              <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
            ) : (
              <span className="material-symbols-outlined text-sm">arrow_upward</span>
            )}
          </button>
        </div>
      </form>
      <div
        id="command-prompt-hint"
        className="mt-1.5 text-[11px] text-[var(--color-text-faint)] text-right pr-4 select-none"
      >
        Press <kbd className="px-1 py-0.5 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[10px] font-mono">Ctrl</kbd>
        <span className="mx-0.5">/</span>
        <kbd className="px-1 py-0.5 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[10px] font-mono">⌘</kbd>
        <span className="mx-1">+</span>
        <kbd className="px-1 py-0.5 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[10px] font-mono">Enter</kbd>
        <span className="ml-1">to send &middot; Enter for new line</span>
      </div>
    </div>
  );
});

CommandPrompt.displayName = 'CommandPrompt';
