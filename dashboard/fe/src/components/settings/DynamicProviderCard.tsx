'use client';

import type { ConfiguredProvider, ProviderSettings } from '@/types/settings';

export interface DynamicProviderCardProps {
  providerId: string;
  provider: ConfiguredProvider;
  settings?: ProviderSettings;
  vaultSet: boolean;
  onVaultClick: () => void;
  onToggle: (enabled: boolean) => void;
  onRemove?: () => void;
}

export function DynamicProviderCard({
  providerId,
  provider,
  settings,
  vaultSet,
  onVaultClick,
  onToggle: _onToggle,
  onRemove,
}: DynamicProviderCardProps) {
  const isEnabled = settings?.enabled ?? true;

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img
            src={provider.logo_url}
            alt={provider.name}
            className="w-5 h-5"
            onError={(e) => {
              (e.target as HTMLImageElement).src = `https://models.dev/logos/${providerId}.svg`;
            }}
          />
          <div>
            <span className="text-xs font-bold uppercase tracking-widest text-slate-900">
              {provider.name}
            </span>
            <span className="text-[10px] text-slate-400 ml-2">
              {Object.keys(provider.models).length} models
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${vaultSet ? 'bg-green-400' : 'bg-slate-300'}`} />
          <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
            isEnabled && vaultSet ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
          }`}>
            {isEnabled && vaultSet ? 'ACTIVE' : 'INACTIVE'}
          </span>
          {onRemove && (
            <button
              onClick={onRemove}
              className="p-0.5 rounded hover:bg-slate-200 transition-colors"
              title="Remove provider"
            >
              <span className="material-symbols-outlined text-sm text-slate-400 hover:text-red-500">close</span>
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-5 space-y-4 flex-1">
        {/* API Key */}
        <div>
          <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block mb-1.5">
            API Key
          </label>
          <button
            onClick={onVaultClick}
            className="w-full bg-slate-50 border border-slate-200 rounded p-2.5 text-xs font-mono text-left flex items-center justify-between hover:bg-slate-100 transition-colors"
          >
            <span className="text-slate-400">
              {vaultSet ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : 'Click to configure'}
            </span>
            <span className={`material-symbols-outlined text-sm ${vaultSet ? 'text-green-600' : 'text-slate-400'}`}>
              {vaultSet ? 'check_circle' : 'vpn_key'}
            </span>
          </button>
        </div>

        {/* Env vars hint */}
        {provider.env.length > 0 && (
          <div className="text-[10px] text-slate-400 flex items-center gap-1">
            <span className="material-symbols-outlined text-xs">terminal</span>
            ENV: <code className="bg-slate-100 px-1 rounded">{provider.env[0]}</code>
          </div>
        )}

        {/* Doc link */}
        {provider.doc && (
          <a
            href={provider.doc}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-blue-600 hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-xs">open_in_new</span>
            Documentation
          </a>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-3 bg-slate-900 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isEnabled && vaultSet ? 'bg-green-400 animate-pulse' : 'bg-slate-500'}`} />
        <span className="text-[10px] font-mono text-slate-400">
          {isEnabled && vaultSet ? 'READY' : 'INACTIVE'}
        </span>
      </div>
    </div>
  );
}
