'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Epic, ChannelMessage as MessageType } from '@/types';
import { useMessages } from '@/hooks/use-messages';
import ChannelMessage from './ChannelMessage';

interface ChannelFeedProps {
  epic: Epic;
}

export default function ChannelFeed({ epic }: ChannelFeedProps) {
  const { messages } = useMessages(epic.plan_id, epic.epic_ref);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  // Group messages by state transitions
  const groupedMessages = (messages || []).reduce((acc: { state?: string, messages: MessageType[] }[], msg) => {
    const lastGroup = acc[acc.length - 1];
    if (!lastGroup || lastGroup.state !== msg.lifecycle_state) {
      acc.push({
        state: msg.lifecycle_state,
        messages: [msg]
      });
    } else {
      lastGroup.messages.push(msg);
    }
    return acc;
  }, []);

  return (
    <footer className="h-80 border-t-4 border-slate-200 bg-terminal-bg flex flex-col shrink-0 overflow-hidden relative">
      {/* Feed Header */}
      <div className="flex items-center justify-between px-6 py-2 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-6">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">forum</span> Channel Feed
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-slate-500">Filters:</span>
            <button className="px-2 py-0.5 bg-slate-800 text-slate-300 text-[10px] rounded hover:bg-slate-700 transition-colors">All</button>
            <button className="px-2 py-0.5 bg-slate-800/50 text-slate-500 text-[10px] rounded hover:bg-slate-700 transition-colors">Tasks</button>
            <button className="px-2 py-0.5 bg-slate-800/50 text-slate-500 text-[10px] rounded hover:bg-slate-700 transition-colors">Escalations</button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="checkbox" 
              checked={autoScroll} 
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-slate-700 bg-slate-800 text-primary focus:ring-0 w-3 h-3" 
            />
            <span className="text-[10px] font-mono text-slate-400">Auto-scroll</span>
          </label>
          <div className="h-4 w-px bg-slate-700"></div>
          <button className="text-slate-500 hover:text-white transition-colors">
            <span className="material-symbols-outlined text-sm">settings</span>
          </button>
        </div>
      </div>

      {/* Action Banner (Optional - based on state or security alerts) */}
      <div className="bg-warning/10 border-b border-warning/20 px-6 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-warning text-lg">lock</span>
          <span className="text-xs font-medium text-warning-light">Action required: Agent requests API key for external service.</span>
        </div>
        <button className="px-4 py-1 bg-primary hover:bg-blue-600 text-white text-[11px] font-bold rounded shadow-lg transition-all active:scale-95">
          Approve Execution
        </button>
      </div>

      {/* Feed Messages */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto terminal-scroll p-6 font-mono text-[13px] leading-relaxed"
        role="log"
        aria-label="Channel activity log"
        aria-live="polite"
      >
        {groupedMessages.map((group, idx) => (
          <div key={idx} className="mb-8 border-l border-slate-800 pl-4 relative">
            <div className="absolute -left-1.5 top-0 w-3 h-3 rounded-full bg-slate-800 border-2 border-terminal-bg"></div>
            <div className="text-[10px] text-slate-500 uppercase tracking-tighter mb-4 font-bold">
              {group.state ? `Transition: ${group.state}` : 'Initial Activity'}
            </div>
            <div className="space-y-4">
              {group.messages.map((msg: MessageType) => (
                <ChannelMessage key={msg.id} message={msg} />
              ))}
            </div>
          </div>
        ))}
        
        {/* Blinking Cursor at bottom */}
        <div className="flex items-center gap-2 text-slate-500 mt-4 font-mono text-[13px]">
           <span className="w-2 h-4 bg-slate-600 animate-pulse"></span>
           <span>Waiting for approval...</span>
        </div>
      </div>
    </footer>
  );
}
