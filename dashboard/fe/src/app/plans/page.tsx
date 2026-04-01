'use client';

import Link from 'next/link';
import PlanGrid from '@/components/dashboard/PlanGrid';
import { Button } from '@/components/ui/Button';

export default function PlansPage() {
  return (
    <div className="p-6 max-w-[1600px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-text-main">
            Plans
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Browse and manage all plans
          </p>
        </div>
        <Link href="/plans/new">
          <Button className="flex items-center gap-2">
            <span className="material-symbols-outlined text-lg">add</span>
            New Plan
          </Button>
        </Link>
      </div>

      {/* Plans */}
      <PlanGrid />
    </div>
  );
}
