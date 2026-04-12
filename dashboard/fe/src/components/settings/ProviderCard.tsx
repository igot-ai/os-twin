'use client';

import { useState, useRef } from 'react';
import { ProvenanceChip } from './ProvenanceChip';
import type { ProviderSettings, GoogleDeploymentMode, ModelInfo } from '@/types/settings';

const PROVIDER_ICONS: Record<string, { icon: string; color: string }> = {
  google: { icon: 'cloud', color: 'text-blue-600' },
  anthropic: { icon: 'psychology', color: 'text-orange-600' },
  openai: { icon: 'hub', color: 'text-green-700' },
};

export interface ProviderCardProps {
  name: string;
  provider: ProviderSettings;
  variant?: 'primary' | 'compact';
  provenance?: string;
  onToggle: (enabled: boolean) => void;
  onModelChange: (model: string) => void;
  onSettingsChange?: (updates: Partial<ProviderSettings>) => void;
  onTest: () => Promise<{ latency_ms: number }>;
  onVaultClick: () => void;
  onServiceAccountUpload?: (jsonContent: string) => Promise<void>;
  vaultSet: boolean;
  serviceAccountVaultSet?: boolean;
  modelRegistry?: ModelInfo[];
  models: string[];   // kept for backward compat
}

export function ProviderCard({
  name,
  provider,
  variant = 'compact',
  provenance,
  onToggle,
  onModelChange,
  onSettingsChange,
  onTest,
  onVaultClick,
  onServiceAccountUpload,
  vaultSet,
  serviceAccountVaultSet = false,
  modelRegistry = [],
  models,
}: ProviderCardProps) {
  const safeProvider = provider ?? { enabled: false, default_model: null };
  const isEnabled = safeProvider.enabled ?? false;
  const defaultModel = safeProvider.default_model ?? '';
  const deploymentMode: GoogleDeploymentMode = (safeProvider.deployment_mode as GoogleDeploymentMode) || 'gemini';
  const projectId = safeProvider.project_id ?? '';
  const vertexLocation = safeProvider.vertex_location ?? 'global';

  const [testing, setTesting] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleTest = async () => {
    setTesting(true);
    setTestError(null);
    try {
      const result = await onTest();
      setLatency(result.latency_ms);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Test failed';
      setTestError(message);
    } finally {
      setTesting(false);
    }
  };

  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setTestError(null);
    try {
      const content = await file.text();
      // Validate it's valid JSON with expected fields
      const parsed = JSON.parse(content);
      if (!parsed.type || !parsed.project_id) {
        throw new Error('Missing required fields (type, project_id)');
      }
      // Store the JSON content in vault
      await onServiceAccountUpload?.(content);
      setUploadedFileName(file.name);
      // Auto-fill project_id from the service account
      if (parsed.project_id) {
        onSettingsChange?.({ project_id: parsed.project_id });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid service account JSON';
      setTestError(message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const meta = PROVIDER_ICONS[name] || { icon: 'memory', color: 'text-slate-600' };

  // ── Google Primary variant with Deployment Mode ───────────────────
  if (variant === 'primary' && name === 'google') {
    // Filter models by deployment mode from registry
    const modeModels = modelRegistry.length > 0
      ? modelRegistry.filter((m) => !m.mode || m.mode === deploymentMode)
      : [];

    return (
      <section className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className={`material-symbols-outlined ${meta.color}`}>{meta.icon}</span>
            <span className="text-xs font-bold uppercase tracking-widest text-slate-900">
              Google Cloud Provisioning
            </span>
          </div>
          <span className={`px-2 py-1 text-[10px] font-bold rounded ${isEnabled ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
            }`}>
            {isEnabled ? 'ACTIVE' : 'INACTIVE'}
          </span>
        </div>

        <div className="p-6 space-y-8">
          {/* ── Deployment Mode Selector ──────────────────────────────── */}
          <div>
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block mb-4">
              Select Deployment Mode
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => {
                  onSettingsChange?.({ deployment_mode: 'gemini', default_model: undefined });
                }}
                className={`flex flex-col p-4 rounded-lg text-left transition-all ${deploymentMode === 'gemini'
                    ? 'border-2 border-blue-600 bg-blue-50/40'
                    : 'border border-slate-200 bg-white hover:border-blue-200'
                  }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className={`text-sm font-bold ${deploymentMode === 'gemini' ? 'text-blue-800' : 'text-slate-900'
                    }`}>GEMINI</span>
                  <span className="material-symbols-outlined text-sm" style={{
                    fontVariationSettings: deploymentMode === 'gemini' ? "'FILL' 1" : "'FILL' 0",
                    color: deploymentMode === 'gemini' ? '#2563eb' : '#94a3b8',
                  }}>
                    {deploymentMode === 'gemini' ? 'radio_button_checked' : 'radio_button_unchecked'}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Optimized for multimodal inference and large context windows via API.
                </p>
              </button>

              <button
                type="button"
                onClick={() => {
                  onSettingsChange?.({ deployment_mode: 'vertex', default_model: undefined });
                }}
                className={`flex flex-col p-4 rounded-lg text-left transition-all ${deploymentMode === 'vertex'
                    ? 'border-2 border-blue-600 bg-blue-50/40'
                    : 'border border-slate-200 bg-white hover:border-blue-200'
                  }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className={`text-sm font-bold ${deploymentMode === 'vertex' ? 'text-blue-800' : 'text-slate-900'
                    }`}>VERTEX AI</span>
                  <span className="material-symbols-outlined text-sm" style={{
                    fontVariationSettings: deploymentMode === 'vertex' ? "'FILL' 1" : "'FILL' 0",
                    color: deploymentMode === 'vertex' ? '#2563eb' : '#94a3b8',
                  }}>
                    {deploymentMode === 'vertex' ? 'radio_button_checked' : 'radio_button_unchecked'}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  Enterprise-grade orchestration with VPC-SC and advanced monitoring.
                </p>
              </button>
            </div>
          </div>

          {/* ── Auth Fields ─────────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-6">
            {/* Auth — mode-dependent */}
            {deploymentMode === 'gemini' ? (
              /* Gemini API: API Key via vault */
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
                  API Access Key
                </label>
                <button
                  onClick={onVaultClick}
                  className="w-full bg-slate-50 border border-slate-200 rounded p-3 text-sm font-mono text-left flex items-center justify-between hover:bg-slate-100 transition-colors"
                >
                  <span className="text-slate-400">
                    {vaultSet ? '••••••••••••••••••••••••' : 'Click to configure'}
                  </span>
                  <span className={`material-symbols-outlined text-sm ${vaultSet ? 'text-green-600' : 'text-slate-400'}`}>
                    {vaultSet ? 'check_circle' : 'vpn_key'}
                  </span>
                </button>
              </div>
            ) : (
              /* Vertex AI: Project ID */
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
                  GCP Project ID
                </label>
                <input
                  type="text"
                  value={projectId}
                  onChange={(e) => onSettingsChange?.({ project_id: e.target.value })}
                  placeholder="my-gcp-project-id"
                  disabled={!isEnabled}
                  className="w-full bg-slate-50 border border-slate-200 rounded p-3 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-900 placeholder:text-slate-400"
                />
              </div>
            )}

            {/* Vertex AI: Location */}
            {deploymentMode === 'vertex' && (
              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
                  Vertex Location
                </label>
                <input
                  type="text"
                  value={vertexLocation}
                  onChange={(e) => onSettingsChange?.({ vertex_location: e.target.value })}
                  placeholder="global"
                  disabled={!isEnabled}
                  className="w-full bg-slate-50 border border-slate-200 rounded p-3 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-900 placeholder:text-slate-400"
                />
                <p className="text-[10px] text-slate-400">
                  Region for Vertex AI. Defaults to &quot;global&quot;.
                </p>
              </div>
            )}
          </div>

          {/* ── Vertex-only: Service Account File Upload ────────────── */}
          {deploymentMode === 'vertex' && (
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
                Service Account JSON
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`flex items-center gap-3 p-3 rounded border-2 border-dashed cursor-pointer transition-colors ${serviceAccountVaultSet
                    ? 'border-green-300 bg-green-50/50 hover:bg-green-50'
                    : 'border-slate-200 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/30'
                  }`}
              >
                <span className={`material-symbols-outlined text-lg ${serviceAccountVaultSet ? 'text-green-600' : 'text-slate-400'
                  }`}>
                  {uploading ? 'hourglass_top' : serviceAccountVaultSet ? 'check_circle' : 'upload_file'}
                </span>
                <div className="flex-1 min-w-0">
                  {uploading ? (
                    <p className="text-xs font-mono text-slate-500">Uploading...</p>
                  ) : serviceAccountVaultSet ? (
                    <>
                      <p className="text-xs font-semibold text-green-700">
                        {uploadedFileName || 'service-account.json'}
                      </p>
                      <p className="text-[10px] text-green-600">Stored securely in vault</p>
                    </>
                  ) : (
                    <>
                      <p className="text-xs font-semibold text-slate-700">
                        Attach service-account.json
                      </p>
                      <p className="text-[10px] text-slate-400">Click to browse or drop your GCP key file</p>
                    </>
                  )}
                </div>
                {serviceAccountVaultSet && (
                  <span className="text-[10px] font-mono text-slate-400 hover:text-blue-600">
                    Replace
                  </span>
                )}
              </div>
              <p className="text-[10px] text-slate-400">
                Required for Vertex AI authentication. Project ID will be auto-filled from the key file.
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleFileSelected}
                className="hidden"
              />
            </div>
          )}
        </div>

        {/* ── Status Bar ─────────────────────────────────────────────── */}
        <div className="mt-auto px-6 py-4 bg-slate-900 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              {testing ? (
                <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
              ) : latency !== null ? (
                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              ) : (
                <div className="w-2 h-2 rounded-full bg-slate-500" />
              )}
              <span className="text-[10px] font-mono text-slate-400">
                {testing ? 'TESTING...' : latency !== null ? `LATENCY: ${latency}ms` : 'READY'}
              </span>
            </div>
            {testError && (
              <span className="text-[10px] font-mono text-red-400 truncate max-w-xs">{testError}</span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              MODE: {deploymentMode.toUpperCase()}
            </span>
            <button
              onClick={handleTest}
              disabled={testing || !isEnabled}
              className="text-[10px] font-mono text-slate-400 hover:text-white transition-colors disabled:opacity-50"
            >
              [RUN TEST]
            </button>
          </div>
        </div>
      </section>
    );
  }

  // ── Generic Primary variant (non-Google) ──────────────────────────
  if (variant === 'primary') {
    const displayModels = modelRegistry.length > 0
      ? modelRegistry
      : models.map((m) => ({ id: m, label: m }));

    return (
      <section className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className={`material-symbols-outlined ${meta.color}`}>{meta.icon}</span>
            <span className="text-xs font-bold uppercase tracking-widest text-slate-900">
              {name} Provisioning
            </span>
          </div>
          <span className={`px-2 py-1 text-[10px] font-bold rounded ${isEnabled ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
            }`}>
            {isEnabled ? 'ACTIVE' : 'INACTIVE'}
          </span>
        </div>

        <div className="p-6 space-y-6">
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block">
              API Access Key
            </label>
            <button
              onClick={onVaultClick}
              className="w-full bg-slate-50 border border-slate-200 rounded p-3 text-sm font-mono text-left flex items-center justify-between hover:bg-slate-100 transition-colors"
            >
              <span className="text-slate-400">
                {vaultSet ? '••••••••••••••••••••••••' : 'Click to configure'}
              </span>
              <span className={`material-symbols-outlined text-sm ${vaultSet ? 'text-green-600' : 'text-slate-400'}`}>
                {vaultSet ? 'check_circle' : 'vpn_key'}
              </span>
            </button>
          </div>
        </div>

        <div className="mt-auto px-6 py-4 bg-slate-900 flex justify-between items-center">
          <div className="flex items-center gap-2">
            {testing ? (
              <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            ) : latency !== null ? (
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            ) : (
              <div className="w-2 h-2 rounded-full bg-slate-500" />
            )}
            <span className="text-[10px] font-mono text-slate-400">
              {testing ? 'TESTING...' : latency !== null ? `LATENCY: ${latency}ms` : 'READY'}
            </span>
          </div>
          <button
            onClick={handleTest}
            disabled={testing || !isEnabled}
            className="text-[10px] font-mono text-slate-400 hover:text-white transition-colors disabled:opacity-50"
          >
            [RUN TEST]
          </button>
        </div>
      </section>
    );
  }

  // ── Compact variant (secondary providers) ─────────────────────────
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-6 relative">
      <div className="absolute left-0 top-6 w-1 h-8" style={{ background: meta.color === 'text-orange-600' ? '#ea580c' : '#16a34a' }} />

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={`material-symbols-outlined ${meta.color}`}>{meta.icon}</span>
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-900">{name}</h3>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block mb-1.5">
            API Access Key
          </label>
          <button
            onClick={onVaultClick}
            className="w-full bg-slate-50 border border-slate-200 rounded p-2.5 text-xs font-mono text-left flex items-center justify-between hover:bg-slate-100 transition-colors"
          >
            <span className="text-slate-400">
              {vaultSet ? '••••••••••••••••••••••••' : 'Click to configure'}
            </span>
            <span className={`material-symbols-outlined text-sm ${vaultSet ? 'text-green-600' : 'text-slate-400'}`}>
              {vaultSet ? 'check_circle' : 'vpn_key'}
            </span>
          </button>
        </div>

        <button
          onClick={handleTest}
          disabled={testing || !isEnabled}
          className="w-full py-2 text-[10px] font-bold uppercase bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-colors disabled:opacity-50"
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </button>

        {latency !== null && (
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-sm text-green-600">check_circle</span>
            <span className="text-[11px] font-mono text-slate-600">Latency: {latency}ms</span>
          </div>
        )}
        {testError && (
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-sm text-red-500">error</span>
            <span className="text-[11px] font-mono text-red-500">{testError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
