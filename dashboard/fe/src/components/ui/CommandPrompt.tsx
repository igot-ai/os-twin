import React, { useState, useRef } from 'react';
import { processImages, MAX_IMAGES, type ProcessedImage } from '@/lib/image-utils';
import type { ImageAttachment } from '@/types';

interface CommandPromptProps {
  onSubmit: (prompt: string, images?: ImageAttachment[]) => void;
  isConversationActive?: boolean;
  value?: string;
  onChange?: (val: string) => void;
  isLoading?: boolean;
}

export const CommandPrompt: React.FC<CommandPromptProps> = ({ onSubmit, isConversationActive = false, value, onChange, isLoading = false }) => {
  const [internalPrompt, setInternalPrompt] = useState('');
  const [pendingImages, setPendingImages] = useState<ProcessedImage[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
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

  const removeImage = (index: number) => {
    setPendingImages(prev => prev.filter((_, i) => i !== index));
    setImageError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const hasText = prompt.trim().length > 0;
    const hasImages = pendingImages.length > 0;
    if (!hasText && !hasImages) return;

    const images: ImageAttachment[] | undefined = hasImages
      ? pendingImages.map(img => ({ url: img.url, name: img.name, type: img.type }))
      : undefined;

    onSubmit(prompt, images);
    if (!isControlled) setInternalPrompt('');
    setPendingImages([]);
    setImageError(null);
  };

  return (
    <div className={isConversationActive ? 'w-full max-w-4xl mx-auto' : 'w-full max-w-2xl mx-auto mt-8'}>
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
          className="p-3 ml-2 text-text-muted hover:text-primary transition-colors active:scale-95 disabled:opacity-30"
          aria-label="Add image"
          disabled={isLoading || pendingImages.length >= MAX_IMAGES}
          onClick={() => fileInputRef.current?.click()}
        >
          <span className="material-symbols-outlined text-xl">add_photo_alternate</span>
        </button>

        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onPaste={handlePaste}
          disabled={isLoading}
          placeholder="What do you want to build?"
          className="flex-1 bg-transparent border-none py-4 px-2 text-[16px] font-[var(--font-display)] text-[var(--color-text-main)] outline-none placeholder:text-[var(--color-text-faint)] transition-all disabled:opacity-50"
        />

        <div className="flex items-center gap-2 pr-4">
          <div className="flex items-center gap-1 px-3 py-1.5 bg-[var(--color-primary-muted)] text-[var(--color-primary)] rounded-[var(--radius-full)] text-sm font-[var(--font-display)] font-medium">
            <span className="material-symbols-outlined text-sm">account_tree</span>
            Plan
          </div>
          <button
            type="submit"
            disabled={(!prompt.trim() && pendingImages.length === 0) || isLoading}
            className="p-2 bg-primary text-white rounded-full hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 active:scale-95 flex items-center justify-center min-w-[36px] min-h-[36px]"
          >
            {isLoading ? (
              <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
            ) : (
              <span className="material-symbols-outlined text-sm">arrow_upward</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
