import React, { useState, useEffect } from 'react';

interface CommandPromptProps {
  onSubmit: (prompt: string) => void;
  isConversationActive?: boolean;
  value?: string;
  onChange?: (val: string) => void;
}

export const CommandPrompt: React.FC<CommandPromptProps> = ({ onSubmit, isConversationActive = false, value, onChange }) => {
  const [internalPrompt, setInternalPrompt] = useState('');

  const isControlled = value !== undefined && onChange !== undefined;
  const prompt = isControlled ? value : internalPrompt;
  const setPrompt = isControlled ? onChange : setInternalPrompt;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    onSubmit(prompt);
    if (!isControlled) setInternalPrompt('');
  };

  return (
    <form 
      onSubmit={handleSubmit}
      className={`relative flex items-center bg-surface/80 backdrop-blur-[12px] border border-border rounded-2xl shadow-card transition-all duration-300 focus-within:ring-4 focus-within:ring-primary-muted focus-within:border-primary hover:border-primary-light ${isConversationActive ? 'w-full max-w-4xl mx-auto' : 'w-full max-w-2xl mx-auto mt-8'}`}
    >
      <button 
        type="button" 
        className="p-3 ml-2 text-text-muted hover:text-primary transition-colors active:scale-95"
        aria-label="Add attachment"
      >
        <span className="material-symbols-outlined text-xl">add_circle</span>
      </button>
      
      <input
        type="text"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="What do you want to build?"
        className="flex-1 bg-transparent border-none py-4 px-2 text-[16px] font-[var(--font-display)] text-[var(--color-text-main)] outline-none placeholder:text-[var(--color-text-faint)] transition-all"
      />
      
      <div className="flex items-center gap-2 pr-4">
        <div className="flex items-center gap-1 px-3 py-1.5 bg-[var(--color-primary-muted)] text-[var(--color-primary)] rounded-[var(--radius-full)] text-sm font-[var(--font-display)] font-medium">
          <span className="material-symbols-outlined text-sm">account_tree</span>
          Plan
        </div>
        <button 
          type="submit"
          disabled={!prompt.trim()}
          className="p-2 bg-primary text-white rounded-full hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 active:scale-95 flex items-center justify-center"
        >
          <span className="material-symbols-outlined text-sm">arrow_upward</span>
        </button>
      </div>
    </form>
  );
};
