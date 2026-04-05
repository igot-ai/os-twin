"use client";

import React, { useRef, useEffect, useState } from 'react';
import { useRouter, usePathname, useParams } from 'next/navigation';
import { usePlanningThread } from '@/hooks/use-planning-thread';
import { AgentResponse } from '@/components/chat/AgentResponse';
import { Button } from '@/components/ui/Button';
import { ImageAttachment } from '@/types';
import { processImages, MAX_IMAGES, type ProcessedImage } from '@/lib/image-utils';

interface IdeaChatProps {
  threadId: string;
}

export function IdeaChat({ threadId: propId }: IdeaChatProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const pathSegments = pathname?.split('/').filter(Boolean);

  // Prefer URL pathname over static params (which may be a template placeholder)
  const TEMPLATE_IDS = new Set(['template']);
  const urlThreadId = (pathSegments?.[0] === 'ideas' && pathSegments?.[1]) ? pathSegments[1] : '';
  const paramsThreadId = params?.threadId as string | undefined;
  const threadId = urlThreadId && !TEMPLATE_IDS.has(urlThreadId)
    ? urlThreadId
    : paramsThreadId && !TEMPLATE_IDS.has(paramsThreadId)
      ? paramsThreadId
      : '';

  const {
    thread,
    messages,
    streamedResponse,
    isStreaming,
    isLoading,
    sendMessage,
    promoteToPlan,
    cancel
  } = usePlanningThread(threadId);

  const [input, setInput] = useState('');
  const [isPromoting, setIsPromoting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showFab, setShowFab] = useState(false);
  const autoTriggeredRef = useRef(false);
  const sendMessageRef = useRef(sendMessage);
  sendMessageRef.current = sendMessage;

  // Image attachment state
  const [pendingImages, setPendingImages] = useState<ProcessedImage[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);

  // Auto-trigger AI response when thread loads with only a user message and no reply
  useEffect(() => {
    if (autoTriggeredRef.current) return;
    if (isLoading || isStreaming) return;
    if (messages.length !== 1) return;
    if (messages[0].role !== 'user') return;

    autoTriggeredRef.current = true;
    // Defer to next tick so React state is settled
    setTimeout(() => sendMessageRef.current(messages[0].content, messages[0].images), 0);
  }, [isLoading, isStreaming, messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamedResponse]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setShowFab(scrollHeight - scrollTop - clientHeight > 100);
  };

  const handleSend = () => {
    const hasText = input.trim().length > 0;
    const hasImages = pendingImages.length > 0;
    if ((!hasText && !hasImages) || isStreaming) return;

    const images: ImageAttachment[] | undefined = hasImages
      ? pendingImages.map(img => ({ url: img.url, name: img.name, type: img.type }))
      : undefined;

    sendMessage(input.trim(), images);
    setInput('');
    setPendingImages([]);
    setImageError(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePromote = async () => {
    setIsPromoting(true);
    try {
      const result = await promoteToPlan();
      if (result?.plan_id) {
        router.push(`/plans/${result.plan_id}`);
      }
    } catch (err) {
      console.error('Failed to promote to plan:', err);
      setIsPromoting(false);
    }
  };

  const handleChipClick = (prompt: string) => {
    setInput(prompt);
    inputRef.current?.focus();
  };

  const addImages = async (files: FileList | File[]) => {
    const remaining = MAX_IMAGES - pendingImages.length;
    if (remaining <= 0) {
      setImageError(`Maximum ${MAX_IMAGES} images allowed.`);
      return;
    }
    const sliced = Array.from(files).slice(0, remaining);
    const { images, errors } = await processImages(sliced);
    if (errors.length > 0) setImageError(errors.join(' '));
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

  const removeImage = (index: number) => {
    setPendingImages(prev => prev.filter((_, i) => i !== index));
    setImageError(null);
  };

  const isPromoted = thread?.status === 'promoted';
  const showChips = messages.length === 0 && !isStreaming;
  const chips = [
    "What problem does this solve?",
    "Who are the users?",
    "What tech stack should we use?"
  ];

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--color-background)' }}>
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b shrink-0" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
        <div className="flex items-center gap-4">
          <Button variant="secondary" size="icon" onClick={() => router.push('/')}>
            <span className="material-symbols-outlined text-lg">arrow_back</span>
          </Button>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-main)' }}>
              {thread?.title || 'New Idea'}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <span
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: isPromoted ? 'rgba(139, 92, 246, 0.1)' : 'var(--color-success-light)',
                  color: isPromoted ? 'var(--color-purple)' : 'var(--color-success-text)'
                }}
              >
                {isPromoted ? 'Promoted' : 'Active'}
              </span>
              {isPromoted && thread?.plan_id && (
                <span
                  className="text-xs cursor-pointer hover:underline"
                  style={{ color: 'var(--color-primary)' }}
                  onClick={() => router.push(`/plans/${thread.plan_id}`)}
                >
                  View Plan &rarr;
                </span>
              )}
            </div>
          </div>
        </div>

        <Button
          variant="primary"
          onClick={handlePromote}
          disabled={isStreaming || isPromoted || isPromoting || messages.length === 0}
          className="gap-2"
        >
          {isPromoting ? (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
          ) : (
            <span className="material-symbols-outlined text-sm">auto_awesome</span>
          )}
          Create Plan
        </Button>
      </header>

      {/* Transcript Area */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar"
      >
        {isLoading && !thread ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--color-primary)' }} />
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-6 pb-20">
            {messages.map((msg, idx) => {
              const isAssistant = msg.role === 'assistant';
              const prevMsg = idx > 0 ? messages[idx - 1] : null;
              const isGrouped = prevMsg?.role === msg.role;

              return (
                <div key={msg.id} className={`flex gap-3 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
                  {isAssistant && !isGrouped && (
                    <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'var(--color-primary-muted)' }}>
                      <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>smart_toy</span>
                    </div>
                  )}
                  {isAssistant && isGrouped && <div className="w-8 shrink-0" />}

                  <div className={`max-w-[80%] ${!isAssistant ? 'text-right' : ''}`}>
                    {!isAssistant ? (
                      <div className="inline-block text-left">
                        {msg.images && msg.images.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mb-1.5 justify-end">
                            {msg.images.map((img, i) => (
                              <img
                                key={i}
                                src={img.url}
                                alt={img.name || 'attachment'}
                                className="w-20 h-20 object-cover rounded-lg cursor-pointer hover:opacity-80 transition-opacity"
                                style={{ border: '1px solid rgba(255,255,255,0.2)' }}
                                onClick={() => window.open(img.url, '_blank')}
                              />
                            ))}
                          </div>
                        )}
                        {msg.content && (
                          <div
                            className="rounded-2xl px-4 py-2 text-sm text-white"
                            style={{ background: 'var(--color-primary)', borderBottomRightRadius: '4px' }}
                          >
                            {msg.content}
                          </div>
                        )}
                      </div>
                    ) : (
                      <AgentResponse content={msg.content} />
                    )}
                  </div>
                </div>
              );
            })}

            {isStreaming && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'var(--color-primary-muted)' }}>
                  <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>smart_toy</span>
                </div>
                <div className="max-w-[80%]">
                  <AgentResponse content={streamedResponse} isStreaming={true} />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {showFab && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-24 right-8 w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-110 z-10"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-main)', border: '1px solid var(--color-border)' }}
        >
          <span className="material-symbols-outlined">arrow_downward</span>
        </button>
      )}

      {/* Composer Area */}
      <div className="p-4 border-t shrink-0" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
        <div className="max-w-4xl mx-auto flex flex-col gap-3">
          {showChips && (
            <div className="flex flex-wrap gap-2 mb-2">
              {chips.map((chip, i) => (
                <button
                  key={i}
                  onClick={() => handleChipClick(chip)}
                  className="text-xs px-3 py-1.5 rounded-full border transition-colors"
                  style={{
                    borderColor: 'var(--color-border)',
                    background: 'var(--color-background)',
                    color: 'var(--color-text-muted)'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.color = 'var(--color-text-main)'}
                  onMouseLeave={(e) => e.currentTarget.style.color = 'var(--color-text-muted)'}
                >
                  {chip}
                </button>
              ))}
            </div>
          )}

          {/* Image preview strip */}
          {pendingImages.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {pendingImages.map((img, i) => (
                <div key={i} className="relative group">
                  <img
                    src={img.url}
                    alt={img.name}
                    className="w-16 h-16 object-cover rounded-lg"
                    style={{ border: '1px solid var(--color-border)' }}
                  />
                  <button
                    onClick={() => removeImage(i)}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ background: 'var(--color-danger, #ef4444)' }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
                  </button>
                  <div className="text-[10px] truncate w-16 mt-0.5 text-center" style={{ color: 'var(--color-text-faint)' }}>
                    {img.name}
                  </div>
                </div>
              ))}
            </div>
          )}
          {imageError && (
            <div className="text-xs" style={{ color: 'var(--color-danger, #ef4444)' }}>{imageError}</div>
          )}

          <div className="relative">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              multiple
              className="hidden"
              onChange={handleFileSelect}
            />

            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              disabled={isStreaming || isPromoted}
              placeholder={isPromoted ? "Thread promoted. View plan to continue." : "Type your message... (Shift+Enter for newline)"}
              className="w-full resize-none rounded-lg pl-11 pr-12 py-3 text-sm focus:outline-none"
              style={{
                background: 'var(--color-background)',
                color: 'var(--color-text-main)',
                border: '1px solid var(--color-border)',
                minHeight: '52px',
                maxHeight: '200px'
              }}
              rows={Math.min(5, input.split('\n').length || 1)}
            />

            {/* Attachment button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming || isPromoted || pendingImages.length >= MAX_IMAGES}
              className="absolute left-2 bottom-2 p-1.5 rounded-md transition-colors disabled:opacity-30"
              style={{ color: 'var(--color-text-muted)' }}
              title="Attach images"
            >
              <span className="material-symbols-outlined text-lg">add_photo_alternate</span>
            </button>

            <div className="absolute right-2 bottom-2">
              {isStreaming ? (
                <Button
                  variant="secondary"
                  size="icon"
                  onClick={cancel}
                  className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                >
                  <span className="material-symbols-outlined text-sm">stop_circle</span>
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="icon"
                  onClick={handleSend}
                  disabled={(!input.trim() && pendingImages.length === 0) || isPromoted}
                  className="h-8 w-8"
                >
                  <span className="material-symbols-outlined text-sm" style={{ transform: 'rotate(-45deg)', marginLeft: '2px', marginBottom: '2px' }}>send</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
