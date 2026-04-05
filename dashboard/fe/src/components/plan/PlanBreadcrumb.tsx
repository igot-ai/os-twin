'use client';

import React from 'react';
import Link from 'next/link';
import { usePlanContext } from './PlanWorkspace';

export default function PlanBreadcrumb() {
  const { plan } = usePlanContext();

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
    </div>
  );
}
