import React, { useRef, useEffect, useState } from 'react';
import { useConversation, Message } from '@/hooks/use-conversation';
import { AgentResponse } from './AgentResponse';

interface ChatHistoryProps {
  conversationId?: string;
  streamingMessage?: string; // Optional message that is currently streaming in
}

export function ChatHistory({ conversationId, streamingMessage }: ChatHistoryProps) {
  const { conversation, isLoading } = useConversation(conversationId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [showFab, setShowFab] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages, streamingMessage]);

  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    // Show FAB if we're scrolled up by more than 100px
    setShowFab(scrollHeight - scrollTop - clientHeight > 100);
  };

  if (isLoading && !conversation) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="loading-container">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--color-primary)' }} />
      </div>
    );
  }

  const messages = conversation?.messages || [];

  return (
    <div className="relative flex-1 flex flex-col min-h-0 overflow-hidden">
      <div 
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar"
      >
        {messages.map((msg, idx) => {
          const isAssistant = msg.role === 'assistant';
          // Group consecutive assistant messages
          const prevMsg = idx > 0 ? messages[idx - 1] : null;
          const isGrouped = prevMsg?.role === msg.role;

          return (
            <div 
              key={msg.id} 
              className={`flex gap-3 ${isAssistant ? 'justify-start' : 'justify-end'}`}
            >
              {isAssistant && !isGrouped && (
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'var(--color-primary-muted)' }}>
                  <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>smart_toy</span>
                </div>
              )}
              {isAssistant && isGrouped && <div className="w-8 shrink-0" />}

              <div className={`max-w-[80%] ${!isAssistant ? 'text-right' : ''}`}>
                {!isAssistant ? (
                  <div 
                    className="rounded-2xl px-4 py-2 text-sm text-left inline-block text-white"
                    style={{ 
                      background: 'var(--color-primary)', 
                      borderBottomRightRadius: '4px' 
                    }}
                  >
                    {msg.content}
                  </div>
                ) : (
                  <AgentResponse content={msg.content} />
                )}
              </div>
            </div>
          );
        })}

        {/* Streaming Placeholder */}
        {streamingMessage && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1" style={{ background: 'var(--color-primary-muted)' }}>
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-primary)' }}>smart_toy</span>
            </div>
            <div className="max-w-[80%]">
              <AgentResponse content={streamingMessage} isStreaming={true} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {showFab && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-6 right-6 w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-110 z-10"
          style={{ background: 'var(--color-surface-elevated)', border: '1px solid var(--color-border)', color: 'var(--color-text-main)' }}
        >
          <span className="material-symbols-outlined text-xl">arrow_downward</span>
        </button>
      )}
    </div>
  );
}
