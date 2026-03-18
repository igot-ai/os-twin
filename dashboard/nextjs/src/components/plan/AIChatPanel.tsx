'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

interface ChatMessage {
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

  // Auto-scroll to bottom on new messages
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
    [handleSend]
  );

  // Extract plan markdown from assistant response
  const extractPlan = (content: string): string => {
    // Try to find markdown code block — use greedy match so inner fenced blocks
    // (e.g. ```text Lifecycle diagrams) don't prematurely end the outer wrapper.
    const codeBlockMatch = content.match(/```(?:markdown)?\n([\s\S]*)```/);
    if (codeBlockMatch) return codeBlockMatch[1].trim();

    // Otherwise if it starts with "# Plan:", use the whole content
    if (content.trim().startsWith('# Plan:')) return content.trim();

    // Try to find the plan section anywhere in the response
    const planMatch = content.match(/(# Plan:[\s\S]*)/);
    if (planMatch) return planMatch[1].trim();

    return content;
  };

  return (
    <div className="ai-chat-panel">
      {/* Header */}
      <div className="ai-chat-header">
        <div className="ai-chat-title">
          <span className="ai-icon">🤖</span>
          <span>Plan Architect</span>
        </div>
        <button className="ai-clear-btn" onClick={onClearHistory} title="Clear chat">
          ✕
        </button>
      </div>

      {/* Messages */}
      <div className="ai-chat-messages">
        {chatHistory.length === 0 && !isRefining && (
          <div className="ai-welcome">
            <div className="ai-welcome-icon">⬡</div>
            <p className="ai-welcome-title">Plan Architect</p>
            <p className="ai-welcome-text">
              Describe your project and I&apos;ll create a structured plan with epics and acceptance
              criteria.
            </p>
            <div className="ai-quick-prompts">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  className="ai-quick-btn"
                  onClick={() => onSendMessage(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {chatHistory.map((msg, i) => (
          <div key={i} className={`ai-msg ai-msg-${msg.role}`}>
            <div className="ai-msg-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>
            <div className="ai-msg-content">
              <pre className="ai-msg-text">{msg.content}</pre>
              {msg.role === 'assistant' && (
                <button
                  className="ai-apply-btn"
                  onClick={() => onApplyToEditor(extractPlan(msg.content))}
                >
                  ✦ Apply to Editor
                </button>
              )}
            </div>
          </div>
        ))}

        {/* Streaming response */}
        {isRefining && streamedResponse && (
          <div className="ai-msg ai-msg-assistant ai-streaming">
            <div className="ai-msg-avatar">🤖</div>
            <div className="ai-msg-content">
              <pre className="ai-msg-text">{streamedResponse}</pre>
              <span className="ai-cursor">▊</span>
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isRefining && !streamedResponse && (
          <div className="ai-msg ai-msg-assistant">
            <div className="ai-msg-avatar">🤖</div>
            <div className="ai-msg-content">
              <div className="ai-thinking">
                <span className="ai-dot"></span>
                <span className="ai-dot"></span>
                <span className="ai-dot"></span>
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="ai-error">
            <span>⚠ {error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="ai-chat-input">
        <textarea
          ref={inputRef}
          className="ai-input-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your plan or ask for refinement..."
          rows={2}
          disabled={isRefining}
        />
        <div className="ai-input-actions">
          {isRefining ? (
            <button className="ai-stop-btn" onClick={onCancel}>
              ■ Stop
            </button>
          ) : (
            <button
              className="ai-send-btn"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              ▶ Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
