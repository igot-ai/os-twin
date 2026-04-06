'use client';

import { Connector, ConnectorInstance } from '@/types';
import { StatusBadge } from '@/components/ui/StatusBadge';
import ConnectorIcon from './ConnectorIcon';

interface ConnectorCardProps {
  instance: ConnectorInstance;
  connector?: Connector;
  onClick: () => void;
}

export default function ConnectorCard({ instance, connector, onClick }: ConnectorCardProps) {
  const isEnabled = instance.enabled;
  const status = instance.credential_status;

  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col p-6 rounded-2xl bg-white border border-slate-200 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300 text-left"
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-xl border flex items-center justify-center overflow-hidden p-1.5 transition-all ${isEnabled ? 'border-primary/20 bg-primary/5' : 'border-slate-200 bg-slate-50 opacity-60'}`}>
          <ConnectorIcon name={connector?.icon || ''} className="w-full h-full" />
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge 
            status={isEnabled ? 'active' : 'inactive'} 
            label={isEnabled ? 'Enabled' : 'Disabled'}
          />
          {status !== 'ok' && (
            <span className="text-[10px] font-black uppercase tracking-tighter text-red-500 bg-red-50 px-1.5 py-0.5 rounded-md ring-1 ring-red-200">
              Auth {status}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1">
        <h3 className="font-bold text-slate-900 group-hover:text-primary transition-colors mb-1">
          {instance.name}
        </h3>
        <p className="text-xs text-slate-500 line-clamp-2">
          {connector?.name || instance.connector_id} • {connector?.version || 'v1.0'}
        </p>
      </div>

      <div className="mt-6 flex items-center justify-between pt-4 border-t border-slate-50">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400">
          <span className="material-symbols-outlined text-sm">settings</span>
          Manage
        </div>
        <span className="material-symbols-outlined text-slate-300 group-hover:translate-x-1 group-hover:text-primary transition-all">
          chevron_right
        </span>
      </div>
    </button>
  );
}
