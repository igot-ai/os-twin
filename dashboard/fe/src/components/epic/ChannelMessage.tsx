'use client';


import { ChannelMessage as MessageType } from '@/types';

interface ChannelMessageProps {
  message: MessageType;
}

export default function ChannelMessage({ message }: ChannelMessageProps) {
  const isSecurity = message.type === 'escalate' || message.from === 'Security';
  
  // Custom colors for different roles based on mockup
  const getSenderColor = (role: string) => {
    switch (role) {
      case 'System': return 'text-terminal-sys';
      case 'Data Analyst': return 'text-purple-400';
      case 'Security': return 'text-yellow-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className={`flex gap-3 items-start p-3 transition-colors ${
      isSecurity ? 'bg-yellow-500/5 border border-yellow-500/20 rounded-md' : 'group'
    }`}>
      {/* Avatar Box */}
      <div className={`w-8 h-8 rounded flex items-center justify-center shrink-0 ${
        isSecurity ? 'bg-yellow-500/20 text-yellow-500' : 'bg-slate-800 text-slate-400 font-bold text-[10px]'
      }`}>
        {isSecurity ? (
          <span className="material-symbols-outlined text-sm">security</span>
        ) : (
          message.from.substring(0, 2).toUpperCase()
        )}
      </div>

      {/* Message Content */}
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-[11px] font-bold ${getSenderColor(message.from)}`}>
            {message.from}
          </span>
          <span className={`text-[9px] px-1 rounded uppercase ${
            isSecurity ? 'bg-yellow-500/20 text-yellow-500' : 'bg-slate-800 text-slate-500'
          }`}>
            {message.type}
          </span>
          <span className="text-[10px] text-slate-600">
             {new Date(message.ts).toLocaleTimeString([], { 
               hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 
             })}
          </span>
        </div>
        
        <div className={`text-[13px] leading-relaxed ${
          isSecurity ? 'text-yellow-100 font-medium' : 'text-terminal-out'
        }`}>
          {/* Simple formatting for code snippets */}
          {message.body.split(/(`[^`]+`)/).map((part, i) => 
            part.startsWith('`') ? (
              <code key={i} className="text-sky-400">{part.slice(1, -1)}</code>
            ) : (
              <span key={i}>{part}</span>
            )
          )}
        </div>
      </div>
    </div>
  );
}
