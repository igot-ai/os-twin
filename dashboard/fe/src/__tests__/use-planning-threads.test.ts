import { renderHook } from '@testing-library/react';
import { usePlanningThreads } from '../hooks/use-planning-threads';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as swr from 'swr';

vi.mock('swr', () => ({
  default: vi.fn()
}));

const mockUseSWR = swr.default as unknown as ReturnType<typeof vi.fn>;

describe('usePlanningThreads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches list of threads', () => {
    mockUseSWR.mockReturnValue({
      data: { threads: [{ id: '1' }], total: 1 },
      error: null,
      isLoading: false
    });

    const { result } = renderHook(() => usePlanningThreads());

    expect(result.current.threads).toEqual([{ id: '1' }]);
    expect(result.current.total).toBe(1);
    expect(result.current.isLoading).toBe(false);
  });
});
