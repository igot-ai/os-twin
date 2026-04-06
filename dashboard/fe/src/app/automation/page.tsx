'use client';

import React, { useState } from 'react';
import { JobDashboard } from '@/components/automation/JobDashboard';
import { CreateJobModal } from '@/components/automation/CreateJobModal';
import { Button } from '@/components/ui/Button';

export default function AutomationPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-border">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-muted text-primary text-[11px] font-bold uppercase tracking-widest border border-primary/20">
            <span className="material-symbols-outlined text-sm">schedule</span>
            Automated Workflows
          </div>
          <h1 className="text-3xl font-extrabold text-text-main tracking-tight">Scheduler Management</h1>
          <p className="text-text-muted text-sm font-medium max-w-xl">
            Configure cron-based automation for your data policies. Monitor execution, manually trigger syncs, and manage your autonomous data pipelines.
          </p>
        </div>
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-2.5 px-6 py-3 rounded-2xl shadow-xl transition-all transform active:scale-95 group"
        >
          <span className="material-symbols-outlined text-xl group-hover:rotate-90 transition-transform duration-300">add</span>
          Create New Job
        </Button>
      </div>

      {/* Main Content */}
      <JobDashboard />

      {/* Modal */}
      <CreateJobModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
    </div>
  );
}
