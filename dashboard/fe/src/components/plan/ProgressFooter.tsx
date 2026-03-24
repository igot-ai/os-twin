'use client';

import React, { useState } from 'react';
import { usePlanContext } from './PlanWorkspace';
import AnalyticsPanel from './AnalyticsPanel';

export default function ProgressFooter() {
  const { plan, isLoading } = usePlanContext();
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  if (isLoading || !plan) {
    return <div className="h-[56px] bg-surface border-t border-border animate-pulse" />;
  }

  const { pct_complete = 0, critical_path = { completed: 0, total: 0 }, active_epics = 0 } = plan;

  // Progress ring variables
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct_complete / 100) * circumference;

  return (
    <div className="relative">
      {/* Sticky Footer */}
      <footer className="h-[56px] bg-surface border-t border-border flex items-center px-6 gap-8 z-20 relative">
        {/* Progress Ring */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                className="text-border"
                strokeWidth="3"
                stroke="currentColor"
                fill="transparent"
                r={radius}
                cx="20"
                cy="20"
              />
              <circle
                className="text-primary transition-all duration-500 ease-out"
                strokeWidth="3"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
                r={radius}
                cx="20"
                cy="20"
              />
            </svg>
            <span className="absolute text-[10px] font-bold text-text-main">
              {Math.round(pct_complete)}%
            </span>
          </div>
          <span className="text-sm font-semibold text-text-main">Progress</span>
        </div>

        <div className="h-6 w-px bg-border" />

        {/* Critical Path */}
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-text-muted font-bold">Critical Path</span>
          <span className="text-sm font-mono text-text-main">
            {critical_path.completed}/{critical_path.total}
          </span>
        </div>

        <div className="h-6 w-px bg-border" />

        {/* Current Wave - Using Wave 1 as placeholder as it's not in Plan type */}
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-text-muted font-bold">Current Wave</span>
          <span className="text-sm font-mono text-text-main underline decoration-primary underline-offset-4">Wave 1</span>
        </div>

        <div className="h-6 w-px bg-border" />

        {/* Active EPICs */}
        <div className="flex flex-col">
          <span className="text-[10px] uppercase tracking-wider text-text-muted font-bold">Active EPICs</span>
          <span className="text-sm font-mono text-text-main">{active_epics} in flight</span>
        </div>

        <div className="flex-1" />

        {/* View Analytics Button */}
        <button
          onClick={() => setIsPanelOpen(!isPanelOpen)}
          className={`px-4 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-2 ${
            isPanelOpen 
              ? 'bg-primary text-white' 
              : 'bg-surface-hover text-text-main hover:bg-surface-active border border-border'
          }`}
        >
          <span className="material-symbols-outlined text-[18px]">
            {isPanelOpen ? 'keyboard_arrow_down' : 'analytics'}
          </span>
          {isPanelOpen ? 'Close Analytics' : 'View Analytics'}
        </button>
      </footer>

      {/* Analytics Panel Overlay */}
      <AnalyticsPanel isOpen={isPanelOpen} onClose={() => setIsPanelOpen(false)} />
    </div>
  );
}
