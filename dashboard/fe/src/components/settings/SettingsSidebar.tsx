'use client';

import { useState } from 'react';
import type { SettingsNamespace } from '@/types/settings';

export interface SettingsSidebarProps {
  activeNamespace: SettingsNamespace;
  onNamespaceChange: (namespace: SettingsNamespace) => void;
}

const NAMESPACE_ITEMS: { id: SettingsNamespace; icon: string; label: string }[] = [
  { id: 'providers',     icon: 'memory',               label: 'Provider Config' },
  { id: 'runtime',       icon: 'settings',             label: 'Runtime' },
  { id: 'memory',        icon: 'storage',              label: 'Memory' },
  { id: 'knowledge',     icon: 'school',               label: 'Knowledge' },
  { id: 'channels',      icon: 'hub',                  label: 'Channels' },
];

export function SettingsSidebar({
  activeNamespace,
  onNamespaceChange,
}: SettingsSidebarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Mobile menu button */}
      <div className="lg:hidden px-4 pt-4">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="w-full px-4 py-2 rounded text-xs font-semibold flex items-center justify-between bg-white border border-slate-200 text-slate-900"
        >
          <span>{NAMESPACE_ITEMS.find((item) => item.id === activeNamespace)?.label}</span>
          <span className="material-symbols-outlined text-sm">
            {mobileMenuOpen ? 'expand_less' : 'expand_more'}
          </span>
        </button>

        {mobileMenuOpen && (
          <div className="mt-2 flex flex-wrap gap-2">
            {NAMESPACE_ITEMS.map((item) => {
              const isActive = activeNamespace === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => { onNamespaceChange(item.id); setMobileMenuOpen(false); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors ${
                    isActive
                      ? 'bg-white text-blue-600 border border-blue-600 shadow-sm'
                      : 'text-slate-500 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                  {item.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col h-full py-4 space-y-2 bg-slate-50 border-r border-slate-200 w-64 shrink-0">
        <div className="px-6 mb-6">
          <div className="flex items-center gap-3 p-2 bg-white rounded-lg shadow-sm">
            <div className="w-8 h-8 rounded bg-blue-50 flex items-center justify-center">
              <span className="material-symbols-outlined text-blue-600 text-lg">memory</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-900">Core Engine</p>
              <p className="text-[9px] font-mono text-slate-500">v1.0.0</p>
            </div>
          </div>
        </div>

        <div className="flex-1 px-4 space-y-1">
          {NAMESPACE_ITEMS.map((item) => {
            const isActive = activeNamespace === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNamespaceChange(item.id)}
                className={`flex items-center gap-3 px-3 py-2 rounded w-full text-left transition-transform duration-200 ${
                  isActive
                    ? 'bg-white text-blue-600 border-l-4 border-blue-600 shadow-sm'
                    : 'text-slate-500 hover:bg-slate-100 hover:translate-x-1'
                }`}
              >
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider">{item.label}</span>
              </button>
            );
          })}
        </div>


      </aside>
    </>
  );
}
