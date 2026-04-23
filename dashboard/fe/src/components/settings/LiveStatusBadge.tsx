'use client';

import { useSharedWebSocket } from '@/components/providers/WebSocketProvider';


export interface LiveStatusBadgeProps {
  className?: string;
}

export function LiveStatusBadge({ className = '' }: LiveStatusBadgeProps) {
  const { isConnected } = useSharedWebSocket();


  return (
    <div
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded font-mono font-bold text-[10px] uppercase tracking-wider ${
        isConnected ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-600'
      } ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${
        isConnected ? 'bg-green-500' : 'bg-orange-500'
      }`} />
      {isConnected ? 'LIVE' : 'STALE'}
    </div>
  );
}
