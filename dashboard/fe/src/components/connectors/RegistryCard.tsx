'use client';

import { Connector } from '@/types';
import ConnectorIcon from './ConnectorIcon';

interface RegistryCardProps {
  connector: Connector;
  onClick: () => void;
}

export default function RegistryCard({ connector, onClick }: RegistryCardProps) {
  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col p-6 rounded-2xl bg-slate-50 border-2 border-dashed border-slate-200 hover:border-primary/50 hover:bg-primary/5 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300 text-left"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="w-12 h-12 rounded-xl bg-white border border-slate-200 flex items-center justify-center group-hover:border-primary/30 group-hover:shadow-sm transition-all overflow-hidden p-1.5">
          <ConnectorIcon name={connector.icon} className="w-full h-full" />
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 group-hover:text-primary/50 transition-colors">
            Available
          </span>
        </div>
      </div>

      <div className="flex-1">
        <h3 className="font-bold text-slate-900 group-hover:text-primary transition-colors mb-1">
          {connector.name}
        </h3>
        <p className="text-xs text-slate-500 line-clamp-2">
          {connector.description}
        </p>
      </div>

      <div className="mt-6 flex items-center justify-between pt-4 border-t border-slate-100 group-hover:border-primary/10">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 group-hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-sm">add_circle</span>
          Connect {connector.name}
        </div>
        <span className="material-symbols-outlined text-slate-300 group-hover:translate-x-1 group-hover:text-primary transition-all">
          chevron_right
        </span>
      </div>
    </button>
  );
}
