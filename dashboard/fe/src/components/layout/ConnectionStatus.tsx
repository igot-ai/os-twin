
import { Tooltip } from '@/components/ui/Tooltip';

export const ConnectionStatus = () => {
  const isMockRealtime = process.env.NEXT_PUBLIC_ENABLE_MOCK_REALTIME === 'true';
  const status = isMockRealtime ? 'connected' : 'off';
  const label = isMockRealtime ? 'Simulated Real-time Connected' : 'Simulated Real-time Off';

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-main/50 border border-border-main">
      <Tooltip content={label} position="bottom">
        <div className="flex items-center gap-2 cursor-help">
          <div 
            className={`w-2 h-2 rounded-full ${isMockRealtime ? 'bg-status-success animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-status-inactive'}`} 
          />
          <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
            {status}
          </span>
        </div>
      </Tooltip>
    </div>
  );
};