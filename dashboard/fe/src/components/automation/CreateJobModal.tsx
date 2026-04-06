'use client';

import React, { useState } from 'react';
import { useScheduler } from '@/hooks/use-scheduler';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

interface CreateJobModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreateJobModal({ isOpen, onClose }: CreateJobModalProps) {
  const { fetchers, processors, reactors, createJob } = useScheduler();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    interval_seconds: 3600,
    task_type: '',
    params: {} as Record<string, any>,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.task_type) return;

    try {
      setIsSubmitting(true);
      await createJob({
        name: formData.name,
        interval_seconds: Number(formData.interval_seconds),
        task_type: formData.task_type,
        task_params: formData.params,
      });
      onClose();
      // Reset form
      setFormData({
        name: '',
        interval_seconds: 3600,
        task_type: '',
        params: {},
      });
    } catch (err) {
      console.error(err);
      alert('Failed to create job.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleParamChange = (key: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      params: { ...prev.params, [key]: value }
    }));
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Automation Job">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-4">
          {/* Job Name */}
          <div className="space-y-1.5">
            <label className="text-sm font-bold text-text-main">Job Name</label>
            <input
              type="text"
              required
              className="w-full px-4 py-2.5 bg-surface border border-border rounded-xl text-sm focus:ring-2 focus:ring-primary focus:border-primary transition-all outline-none"
              placeholder="e.g. Sync Gmail to Notion"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          {/* Schedule */}
          <div className="space-y-1.5">
            <label className="text-sm font-bold text-text-main">Schedule Interval (Seconds)</label>
            <div className="flex gap-2">
              <input
                type="number"
                min="60"
                required
                className="flex-1 px-4 py-2.5 bg-surface border border-border rounded-xl text-sm focus:ring-2 focus:ring-primary focus:border-primary transition-all outline-none"
                value={formData.interval_seconds}
                onChange={(e) => setFormData({ ...formData, interval_seconds: Number(e.target.value) })}
              />
              <select 
                className="px-4 py-2.5 bg-surface border border-border rounded-xl text-sm outline-none cursor-pointer"
                onChange={(e) => setFormData({ ...formData, interval_seconds: Number(e.target.value) })}
                value={formData.interval_seconds}
              >
                <option value={300}>Every 5m</option>
                <option value={3600}>Every 1h</option>
                <option value={86400}>Every 24h</option>
              </select>
            </div>
          </div>

          {/* Task Type */}
          <div className="space-y-1.5">
            <label className="text-sm font-bold text-text-main">Workflow Type</label>
            <select
              required
              className="w-full px-4 py-2.5 bg-surface border border-border rounded-xl text-sm focus:ring-2 focus:ring-primary focus:border-primary transition-all outline-none cursor-pointer"
              value={formData.task_type}
              onChange={(e) => setFormData({ ...formData, task_type: e.target.value })}
            >
              <option value="">Select a fetcher-processor-reactor flow</option>
              {fetchers?.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>

          {/* Dynamic Params (Optional) */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-bold text-text-main">Workflow Parameters (JSON)</label>
              <span className="text-[10px] text-text-muted font-medium uppercase tracking-wider">Optional</span>
            </div>
            <textarea
              className="w-full px-4 py-2.5 bg-surface border border-border rounded-xl text-xs font-mono focus:ring-2 focus:ring-primary focus:border-primary transition-all outline-none min-h-[100px]"
              placeholder='{ "source": "inbox", "query": "is:unread" }'
              onChange={(e) => {
                try {
                  const val = JSON.parse(e.target.value);
                  setFormData(prev => ({ ...prev, params: val }));
                } catch {
                  // Wait for valid JSON
                }
              }}
            />
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose} className="flex-1 rounded-xl">
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting} className="flex-1 rounded-xl">
            Create Job
          </Button>
        </div>
      </form>
    </Modal>
  );
}
