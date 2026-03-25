'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AIChatPanelProps {
  chatHistory: ChatMessage[];
  isRefining: boolean;
  streamedResponse: string;
  error: string | null;
  onSendMessage: (message: string) => void;
  onApplyToEditor: (content: string) => void;
  onCancel: () => void;
  onClearHistory: () => void;
}

const QUICK_PROMPTS = [
  'Break this into epics',
  'Add acceptance criteria',
  'Add more detail',
  'Simplify the plan',
];

function extractPlan(content: string): string {
  const codeBlockMatch = content.match(/```(?:markdown)?\n([\s\S]*)```/);
  if (codeBlockMatch) return codeBlockMatch[1].trim();

  if (content.trim().startsWith('# Plan:')) return content.trim();

  const planMatch = content.match(/(# Plan:[\s\S]*)/);
  if (planMatch) return planMatch[1].trim();

  return content;
}

function ThinkingDots() {
  return (
    <span className="inline-flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-text-faint"
          style={{
            animation: 'thinking-bounce 1.4s infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes thinking-bounce {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </span>
  );
}

function AssistantAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-primary-muted flex items-center justify-center shrink-0">
      <span className="material-symbols-outlined text-primary" style={{ fontSize: 16 }}>
        smart_toy
      </span>
    </div>
  );
}

export default function AIChatPanel({
  chatHistory,
  isRefining,
  streamedResponse,
  error,
  onSendMessage,
  onApplyToEditor,
  onCancel,
  onClearHistory,
}: AIChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory.length, streamedResponse]);

  const handleSend = useCallback(() => {
    const msg = input.trim();
    if (!msg || isRefining) return;
    setInput('');
    onSendMessage(msg);
  }, [input, isRefining, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">smart_toy</span>
          <span className="text-sm font-semibold text-text-main">Plan Architect</span>
        </div>
        <span
          className="material-symbols-outlined text-text-faint hover:text-text-main cursor-pointer"
          onClick={onClearHistory}
          title="Clear chat"
        >
          close
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {chatHistory.length === 0 && !isRefining && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <span className="material-symbols-outlined text-4xl text-primary mb-3">hub</span>
            <p className="text-base font-semibold text-text-main mb-1">Plan Architect</p>
            <p className="text-sm text-text-muted mb-4">
              Describe your project and I&apos;ll create a structured plan with epics and acceptance
              criteria.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  className="text-xs px-3 py-1.5 rounded-full border border-border hover:border-primary hover:text-primary transition-colors bg-surface"
                  onClick={() => onSendMessage(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {chatHistory.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex gap-3 justify-end">
              <div className="bg-primary text-white rounded-2xl rounded-tr-sm px-4 py-2 max-w-[85%] text-sm">
                <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
              </div>
            </div>
          ) : (
            <div key={i} className="flex gap-3">
              <AssistantAvatar />
              <div>
                <div className="bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-2 max-w-[85%] text-sm text-text-main">
                  <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
                </div>
                <button
                  className="text-xs text-primary hover:text-primary-hover font-medium mt-1.5 flex items-center gap-1"
                  onClick={() => onApplyToEditor(extractPlan(msg.content))}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                    edit_note
                  </span>
                  Apply to Editor
                </button>
              </div>
            </div>
          ),
        )}

        {/* Streaming response */}
        {isRefining && streamedResponse && (
          <div className="flex gap-3">
            <AssistantAvatar />
            <div className="bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-2 max-w-[85%] text-sm text-text-main">
              <pre className="whitespace-pre-wrap font-sans text-sm">{streamedResponse}</pre>
              <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-0.5 align-middle" />
            </div>
          </div>
        )}

        {/* Thinking indicator */}
        {isRefining && !streamedResponse && (
          <div className="flex gap-3">
            <AssistantAvatar />
            <div className="bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-2 text-sm text-text-main">
              <ThinkingDots />
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-danger-light text-danger-text rounded-lg px-3 py-2 text-xs flex items-center gap-2">
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
              warning
            </span>
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border p-3">
        <textarea
          ref={inputRef}
          className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-main placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your plan or ask for refinement..."
          rows={2}
          disabled={isRefining}
        />
        <div className="flex justify-end mt-2">
          {isRefining ? (
            <button
              className="px-3 py-1.5 rounded-lg bg-danger text-white text-xs font-medium"
              onClick={onCancel}
            >
              Stop
            </button>
          ) : (
            <button
              className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary-hover disabled:opacity-50"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
