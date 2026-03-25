'use client';

import React from 'react';
import Link from 'next/link';
import { usePlanContext } from './PlanWorkspace';

export default function PlanBreadcrumb() {
  const { plan, isAIChatOpen, setIsAIChatOpen, isRefining } = usePlanContext();

  return (
    <div className="flex items-center justify-between w-full">
      <nav className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider">
        <Link 
          href="/" 
          className="text-text-muted hover:text-primary transition-colors flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-[14px]">dashboard</span>
          Dashboard
        </Link>
        <span className="material-symbols-outlined text-[14px] text-border">chevron_right</span>
        <span className="text-text-main flex items-center gap-1">
          <span className="material-symbols-outlined text-[14px]">inventory_2</span>
          {plan?.title || 'Plan Detail'}
        </span>
      </nav>

      <button
        onClick={() => setIsAIChatOpen((prev: boolean) => !prev)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all relative ${
          isAIChatOpen
            ? 'bg-primary text-white shadow-lg shadow-primary/20'
            : 'bg-surface-hover text-text-muted hover:text-text-main border border-border/50'
        } ${isRefining ? 'animate-pulse' : ''}`}
      >
        {isRefining && (
          <span className="absolute inset-0 rounded-md bg-primary/20 animate-ping pointer-events-none" />
        )}
        <span className={`material-symbols-outlined text-[18px] ${isRefining ? 'animate-spin' : ''}`}>
          {isRefining ? 'progress_activity' : 'smart_toy'}
        </span>
        <span>AI Architect</span>
        {isAIChatOpen && (
          <span className="w-1.5 h-1.5 rounded-full bg-white ml-1 animate-pulse" />
        )}
      </button>
    </div>
  );
}
