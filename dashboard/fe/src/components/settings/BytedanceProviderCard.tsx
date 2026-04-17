'use client';

import type { ProviderSettings, ModelInfo } from '@/types/settings';

export interface BytedanceProviderCardProps {
  provider: ProviderSettings;
  onSettingsChange: (updates: Partial<ProviderSettings>) => void;
  onVaultClick: () => void;
  vaultSet: boolean;
  modelRegistry?: ModelInfo[];
}

const REGIONS = [
  { id: 'ap-southeast-1', label: 'Singapore', code: 'SG' },
] as const;

export function BytedanceProviderCard({
  provider,
  onSettingsChange,
  onVaultClick,
  vaultSet,
  modelRegistry: _modelRegistry = [],
}: BytedanceProviderCardProps) {
  const safeProvider = provider ?? { enabled: false, default_model: null };
  const isEnabled = safeProvider.enabled ?? false;
  const selectedRegion = safeProvider.base_url || 'cn-beijing-1';

  return (
    <section className="lg:col-span-12 bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col md:flex-row overflow-hidden">
      {/* ── Dark Left Panel ──────────────────────────────────────── */}
      <div className="md:w-1/3 bg-slate-900 p-8 text-white flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-6">
            <span className="material-symbols-outlined text-blue-400">rocket_launch</span>
            <h3 className="text-sm font-bold uppercase tracking-widest">Bytedance (Ark)</h3>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed mb-6">
            Provisioning high-throughput models for the APAC region with localized compliance and low-latency egress.
          </p>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-xs text-green-400">check_circle</span>
              <span className="text-[11px] font-mono text-slate-300">
                Region: {selectedRegion}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-xs text-green-400">check_circle</span>
              <span className="text-[11px] font-mono text-slate-300">
                Endpoint: Ark API
              </span>
            </div>
            {vaultSet && (
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-xs text-green-400">check_circle</span>
                <span className="text-[11px] font-mono text-slate-300">API Key: Configured</span>
              </div>
            )}
          </div>
        </div>

        {/* Status bar */}
        <div className="mt-8 pt-6 border-t border-slate-800">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isEnabled ? 'bg-green-400 animate-pulse' : 'bg-slate-500'}`} />
            <span className="text-[10px] font-mono text-slate-400">
              {isEnabled ? 'READY' : 'INACTIVE'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Right Configuration Panel ────────────────────────────── */}
      <div className="flex-1 p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="space-y-6">
          {/* Deployment Region */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
              Deployment Region
            </label>
            <div className="flex gap-2">
              {REGIONS.map((region) => (
                <button
                  key={region.id}
                  type="button"
                  onClick={() => onSettingsChange({ base_url: region.id })}
                  className={`flex-1 py-3 px-4 border rounded text-xs font-bold flex items-center justify-center gap-2 transition-colors ${selectedRegion === region.id
                      ? 'border-slate-300 bg-slate-50 text-slate-900'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                    }`}
                >
                  <span className="text-xs font-mono text-slate-400">{region.code}</span>
                  {region.label}
                </button>
              ))}
            </div>
          </div>

          {/* Regional Endpoint API Key */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
              Regional Endpoint API Key
            </label>
            <button
              onClick={onVaultClick}
              className="w-full bg-slate-50 border border-slate-200 rounded py-3 px-4 text-xs font-mono text-left flex items-center gap-3 hover:bg-slate-100 transition-colors"
            >
              <span className="material-symbols-outlined text-sm text-slate-400">vpn_key</span>
              <span className="text-slate-400 flex-1">
                {vaultSet ? '••••••••••••••••••••••••' : 'Enter Bytedance Access Token'}
              </span>
              <span className={`material-symbols-outlined text-sm ${vaultSet ? 'text-green-600' : 'text-slate-400'}`}>
                {vaultSet ? 'check_circle' : 'lock'}
              </span>
            </button>
          </div>
        </div>

        {/* Info Panel */}
        <div className="bg-slate-50 border border-dashed border-slate-200 rounded p-6 flex flex-col justify-center items-center text-center space-y-4">
          <span className="material-symbols-outlined text-3xl text-slate-400">info</span>
          <div>
            <p className="text-xs font-bold text-slate-900 mb-1">Regional Optimization Required</p>
            <p className="text-[11px] text-slate-500">
              Deploying to Bytedance Ark requires valid enterprise verification for the selected region.
            </p>
          </div>
          <a
            href="https://docs.byteplus.com/en/docs/ModelArk/1099455"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-2 bg-slate-900 text-white text-[10px] font-bold uppercase tracking-widest rounded hover:bg-slate-800 transition-colors inline-block"
          >
            Learn More
          </a>
        </div>
      </div>
    </section>
  );
}
