'use client';

import React from 'react';

export default function TabPlaceholder({ name, icon }: { name: string; icon: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-10 text-center animate-in fade-in duration-500">
      <div className="w-20 h-20 rounded-full bg-surface-alt border-2 border-dashed border-border flex items-center justify-center mb-6 shadow-inner">
        <span className="material-symbols-outlined text-4xl text-text-faint">{icon}</span>
      </div>
      <h2 className="text-2xl font-black text-text-main mb-3 uppercase tracking-tight">{name}</h2>
      <p className="text-sm text-text-muted max-w-sm font-medium leading-relaxed">
        The {name.toLowerCase()} module is being calibrated for optimal performance. Interactive components will be available in the next cycle.
      </p>
      
      <div className="mt-8 flex gap-3">
        <div className="px-4 py-2 rounded-lg bg-surface border border-border text-[10px] font-bold text-text-faint uppercase tracking-widest animate-pulse">
          Status: Synchronizing
        </div>
      </div>
    </div>
  );
}
