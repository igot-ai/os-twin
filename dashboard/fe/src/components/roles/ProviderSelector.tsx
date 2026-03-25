'use client';

type Provider = 'claude' | 'gpt' | 'gemini' | 'custom';

interface ProviderSelectorProps {
  value: Provider;
  onChange: (value: Provider) => void;
}

const providers: { id: Provider; label: string; icon: string; color: string; bgColor: string }[] = [
  { id: 'claude', label: 'Anthropic', icon: '🟡', color: '#D97706', bgColor: '#FEF3C7' },
  { id: 'gpt', label: 'OpenAI', icon: '🟢', color: '#10B981', bgColor: '#D1FAE5' },
  { id: 'gemini', label: 'Google', icon: '🟣', color: '#6366F1', bgColor: '#E0E7FF' },
  { id: 'custom', label: 'Custom', icon: '⚪', color: '#64748b', bgColor: '#f1f5f9' },
];

export default function ProviderSelector({ value, onChange }: ProviderSelectorProps) {
  return (
    <div className="grid grid-cols-2 gap-3 mb-4">
      {providers.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onChange(p.id)}
          className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left ${
            value === p.id 
              ? 'border-primary shadow-sm bg-primary/5 ring-1 ring-primary/20' 
              : 'border-transparent hover:border-slate-100 hover:bg-slate-50'
          }`}
          style={{ background: value === p.id ? `${p.color}08` : 'var(--color-surface)', borderColor: value === p.id ? p.color : 'var(--color-border)' }}
        >
          <div 
            className="w-10 h-10 rounded-lg flex items-center justify-center text-xl shadow-inner shrink-0"
            style={{ background: p.bgColor }}
          >
            {p.icon}
          </div>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider mb-0.5" style={{ color: p.color }}>{p.label}</div>
            <div className="text-sm font-extrabold capitalize" style={{ color: 'var(--color-text-main)' }}>{p.id}</div>
          </div>
          {value === p.id && (
            <div className="ml-auto">
              <span className="material-symbols-outlined text-base" style={{ color: p.color }}>check_circle</span>
            </div>
          )}
        </button>
      ))}
    </div>
  );
}
