'use client';

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-[1000px] mx-auto fade-in-up">
        <h1 className="text-xl font-extrabold mb-6" style={{ color: 'var(--color-text-main)' }}>Settings</h1>
        
        {/* API Configuration */}
        <section className="rounded-xl border p-5 mb-4" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
          <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
            <span className="material-symbols-outlined text-base">api</span>
            API Configuration
          </h2>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'var(--color-text-faint)' }}>Backend URL</label>
              <div className="flex items-center gap-2">
                <div className="flex-1 px-3 py-2 rounded-md text-xs font-mono" style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-main)' }}>
                  http://localhost:9000/api
                </div>
                <div className="flex items-center gap-1 px-2 py-1.5 rounded text-[10px] font-bold" style={{ background: 'rgba(16, 185, 129, 0.08)', color: 'var(--color-success)' }}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-success)' }} />
                  Connected
                </div>
              </div>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider mb-1 block" style={{ color: 'var(--color-text-faint)' }}>WebSocket URL</label>
              <div className="px-3 py-2 rounded-md text-xs font-mono" style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-main)' }}>
                ws://localhost:9000/api/ws
              </div>
            </div>
          </div>
        </section>

        {/* Theme */}
        <section className="rounded-xl border p-5 mb-4" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
          <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
            <span className="material-symbols-outlined text-base">palette</span>
            Appearance
          </h2>
          <div className="flex gap-3">
            <button className="flex-1 p-4 rounded-lg border-2 flex flex-col items-center gap-2" style={{ borderColor: 'var(--color-primary)', background: 'var(--color-primary-muted)' }}>
              <span className="material-symbols-outlined text-2xl" style={{ color: 'var(--color-primary)' }}>light_mode</span>
              <span className="text-xs font-semibold" style={{ color: 'var(--color-primary)' }}>Light</span>
            </button>
            <button className="flex-1 p-4 rounded-lg border flex flex-col items-center gap-2" style={{ borderColor: 'var(--color-border)' }}>
              <span className="material-symbols-outlined text-2xl" style={{ color: 'var(--color-text-faint)' }}>dark_mode</span>
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-faint)' }}>Dark</span>
            </button>
            <button className="flex-1 p-4 rounded-lg border flex flex-col items-center gap-2" style={{ borderColor: 'var(--color-border)' }}>
              <span className="material-symbols-outlined text-2xl" style={{ color: 'var(--color-text-faint)' }}>computer</span>
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-faint)' }}>System</span>
            </button>
          </div>
        </section>

        {/* Model Registry */}
        <section className="rounded-xl border p-5" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
          <h2 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-main)' }}>
            <span className="material-symbols-outlined text-base">key</span>
            API Keys
          </h2>
          <div className="space-y-3">
            {[
              { name: 'Anthropic (Claude)', status: 'configured', key: 'sk-ant-••••••••' },
              { name: 'OpenAI (GPT)', status: 'configured', key: 'sk-proj-••••••••' },
              { name: 'Google (Gemini)', status: 'missing', key: '' },
            ].map((api) => (
              <div key={api.name} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--color-background)' }}>
                <div>
                  <div className="text-xs font-semibold" style={{ color: 'var(--color-text-main)' }}>{api.name}</div>
                  {api.key && <div className="text-[10px] font-mono" style={{ color: 'var(--color-text-faint)' }}>{api.key}</div>}
                </div>
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{
                    background: api.status === 'configured' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                    color: api.status === 'configured' ? 'var(--color-success)' : 'var(--color-danger)',
                  }}
                >
                  {api.status === 'configured' ? '✓ Configured' : '✗ Missing'}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
  );
}
