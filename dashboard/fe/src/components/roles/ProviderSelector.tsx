'use client';

type Provider = 'claude' | 'gpt' | 'gemini' | 'custom';

const PROVIDER_STATUS_KEY: Record<Provider, string | null> = {
  claude: 'Claude',
  gpt: 'GPT',
  gemini: 'Gemini',
  custom: null,
};

interface ProviderSelectorProps {
  value: Provider;
  onChange: (value: Provider) => void;
  apiKeysStatus?: Record<string, boolean>;
}

const providers: { id: Provider; label: string; icon: string; color: string; bgColor: string }[] = [
  { id: 'claude', label: 'Anthropic', icon: '🟡', color: '#D97706', bgColor: '#FEF3C7' },
  { id: 'gpt', label: 'OpenAI', icon: '🟢', color: '#10B981', bgColor: '#D1FAE5' },
  { id: 'gemini', label: 'Google', icon: '🟣', color: '#6366F1', bgColor: '#E0E7FF' },
  { id: 'custom', label: 'Custom', icon: '⚪', color: '#64748b', bgColor: '#f1f5f9' },
];

export default function ProviderSelector({ value, onChange, apiKeysStatus }: ProviderSelectorProps) {
  const isConfigured = (id: Provider) => {
    const statusKey = PROVIDER_STATUS_KEY[id];
    if (!statusKey) return true; // custom always available
    if (!apiKeysStatus) return true; // still loading, don't block
    return !!apiKeysStatus[statusKey];
  };

  return (
    <div className="grid grid-cols-2 gap-3 mb-4">
      {providers.map((p) => {
        const configured = isConfigured(p.id);
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => configured && onChange(p.id)}
            disabled={!configured}
            className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left ${
              !configured
                ? 'opacity-40 cursor-not-allowed grayscale'
                : value === p.id
                  ? 'border-primary shadow-sm bg-primary/5 ring-1 ring-primary/20'
                  : 'border-transparent hover:border-slate-100 hover:bg-slate-50'
            }`}
            style={{ background: value === p.id && configured ? `${p.color}08` : 'var(--color-surface)', borderColor: value === p.id && configured ? p.color : 'var(--color-border)' }}
          >
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center text-xl shadow-inner shrink-0"
              style={{ background: p.bgColor }}
            >
              {p.icon}
            </div>
            <div className="min-w-0">
              <div className="text-[11px] font-bold uppercase tracking-wider mb-0.5" style={{ color: configured ? p.color : 'var(--color-text-faint)' }}>{p.label}</div>
              <div className="text-sm font-extrabold capitalize" style={{ color: configured ? 'var(--color-text-main)' : 'var(--color-text-faint)' }}>{p.id}</div>
            </div>
            {configured && value === p.id && (
              <div className="ml-auto">
                <span className="material-symbols-outlined text-base" style={{ color: p.color }}>check_circle</span>
              </div>
            )}
            {!configured && (
              <div className="ml-auto">
                <span className="text-[9px] font-bold text-red-400 uppercase">No Key</span>
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
