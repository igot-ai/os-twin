import useSWR from 'swr';
import { AutomationJob, CreateJobRequest } from '@/types';
import { apiPost, apiDelete } from '@/lib/api-client';

export function useScheduler() {
  const { data: jobs, error, mutate, isLoading } = useSWR<AutomationJob[]>('/scheduler/jobs');

  const { data: fetchers } = useSWR<string[]>('/scheduler/policy/fetchers');
  const { data: processors } = useSWR<string[]>('/scheduler/policy/processors');
  const { data: reactors } = useSWR<string[]>('/scheduler/policy/reactors');

  const createJob = async (job: CreateJobRequest) => {
    const newJob = await apiPost<AutomationJob>('/scheduler/jobs', job);
    mutate((current) => (current ? [...current, newJob] : [newJob]), { revalidate: false });
    return newJob;
  };

  const deleteJob = async (jobId: string) => {
    await apiDelete(`/scheduler/jobs/${jobId}`);
    mutate((current) => (current ? current.filter(j => j.job_id !== jobId) : []), { revalidate: false });
  };

  const triggerJob = async (jobId: string) => {
    await apiPost(`/scheduler/jobs/${jobId}/trigger`, {});
  };

  return {
    jobs,
    fetchers,
    processors,
    reactors,
    isLoading,
    isError: error,
    createJob,
    deleteJob,
    triggerJob,
    refresh: mutate,
  };
}
