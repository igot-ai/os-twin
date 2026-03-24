'use client';

import StatsRow from '@/components/dashboard/StatsRow';
import PlanGrid from '@/components/dashboard/PlanGrid';
import { Button } from '@/components/ui/Button';

export default function DashboardPage() {
  return (
    <div className="p-6 max-w-[1600px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-text-main">
            Command Center
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Overview of all active plans and agentic operations
          </p>
        </div>
        <Button 
          className="flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-lg">add</span>
          New Plan
        </Button>
      </div>

      {/* Stats Row */}
      <StatsRow />

      {/* Plan Section */}
      <div className="mt-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-text-main">Active Plans</h2>
        </div>
        
        <PlanGrid />
      </div>
    </div>
  );
}
