'use client';

import React from 'react';
import { useMessages } from '@/hooks/use-messages';
import { AnimatePresence, motion } from 'framer-motion';

interface MessageFeedProps {
  planId: string;
  epicRef: string;
}

const roleColors: Record<string, string> = {
  System: '#38bdf8',
  'Data Analyst': '#8b5cf6',
  Security: '#f59e0b',
  QA: '#10b981',
  Engineer: '#3b82f6',
  Manager: '#64748b',
};

function formatTime(ts: string) {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function MessageFeed({ planId, epicRef }: MessageFeedProps) {
  const { messages, isLoading } = useMessages(planId, epicRef);

  if (isLoading && !messages) {
    return (
      <div className="space-y-4 p-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="animate-pulse flex gap-3 items-start">
            <div className="w-8 h-8 rounded bg-border/20 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-24 bg-border/20 rounded" />
              <div className="h-10 w-full bg-border/10 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <AnimatePresence initial={false} mode="popLayout">
        {messages?.map((msg) => {
          const rc = roleColors[msg.from] || '#64748b';
          const isEscalation = msg.type === 'escalate';

          return (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              layout
              className={`flex gap-3 items-start ${isEscalation ? 'p-3 rounded-md' : ''}`}
              style={isEscalation ? {
                background: 'rgba(245, 158, 11, 0.04)',
                border: '1px solid rgba(245, 158, 11, 0.15)',
              } : {}}
            >
              <div
                className="w-8 h-8 rounded flex items-center justify-center text-[10px] font-bold shrink-0"
                style={{
                  background: isEscalation ? 'rgba(245, 158, 11, 0.15)' : '#1e293b',
                  color: isEscalation ? '#f59e0b' : '#94a3b8',
                }}
              >
                {isEscalation ? (
                  <span className="material-symbols-outlined text-sm">security</span>
                ) : msg.from.slice(0, 3).toUpperCase()}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[11px] font-bold" style={{ color: rc }}>{msg.from}</span>
                  <span
                    className="text-[9px] px-1 rounded uppercase"
                    style={{
                      background: isEscalation ? 'rgba(245, 158, 11, 0.15)' : '#1e293b',
                      color: isEscalation ? '#f59e0b' : '#475569',
                    }}
                  >
                    {msg.type.replace('-', ' ')}
                  </span>
                  <span className="text-[10px]" style={{ color: '#64748b' }}>
                    {formatTime(msg.ts)}
                  </span>
                </div>
                <div className={`text-xs leading-relaxed ${isEscalation ? 'text-text-main' : 'text-text-muted'}`}>
                  {msg.body}
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}