import { describe, it, expect, vi } from 'vitest';
import { useScheduler } from '../hooks/use-scheduler';
import useSWR from 'swr';
import { apiPost, apiDelete } from '@/lib/api-client';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

describe('useScheduler', () => {
  it('should return jobs data', () => {
    const mockJobs = [
      { job_id: '1', name: 'Test Job', interval_seconds: 3600, task_type: 'flow1', enabled: true, task_params: {} }
    ];
    (useSWR as any).mockImplementation((url: string) => {
      if (url === '/scheduler/jobs') return { data: mockJobs, isLoading: false };
      return { data: [], isLoading: false };
    });

    const { jobs } = useScheduler();
    expect(jobs).toEqual(mockJobs);
  });

  it('should create a job', async () => {
    const mockMutate = vi.fn();
    (useSWR as any).mockReturnValue({ mutate: mockMutate });
    
    const newJobRequest = {
      name: 'New Job',
      interval_seconds: 60,
      task_type: 'flow2',
      task_params: { key: 'val' }
    };
    
    const mockResponse = { ...newJobRequest, job_id: '2', enabled: true };
    (apiPost as any).mockResolvedValue(mockResponse);

    const { createJob } = useScheduler();
    await createJob(newJobRequest);

    expect(apiPost).toHaveBeenCalledWith('/scheduler/jobs', newJobRequest);
    expect(mockMutate).toHaveBeenCalled();
  });

  it('should delete a job', async () => {
    const mockMutate = vi.fn();
    (useSWR as any).mockReturnValue({ mutate: mockMutate });
    
    const { deleteJob } = useScheduler();
    await deleteJob('1');

    expect(apiDelete).toHaveBeenCalledWith('/scheduler/jobs/1');
    expect(mockMutate).toHaveBeenCalled();
  });

  it('should trigger a job', async () => {
    const { triggerJob } = useScheduler();
    await triggerJob('1');

    expect(apiPost).toHaveBeenCalledWith('/scheduler/jobs/1/trigger', {});
  });
});
