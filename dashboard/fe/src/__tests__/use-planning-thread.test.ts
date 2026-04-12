import { renderHook } from '@testing-library/react';
import { usePlanningThread } from '../hooks/use-planning-thread';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as swr from 'swr';

vi.mock('swr', () => ({
  default: vi.fn()
}));

const mockUseSWR = swr.default as unknown as ReturnType<typeof vi.fn>;

describe('usePlanningThread', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('initializes with default values', () => {
    mockUseSWR.mockReturnValue({
      data: null,
      error: null,
      mutate: vi.fn(),
      isLoading: false
    });

    const { result } = renderHook(() => usePlanningThread('test-id'));

    expect(result.current.thread).toBeUndefined();
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.streamedResponse).toBe('');
    expect(result.current.error).toBeNull();
  });

  it('returns server messages when available', () => {
    const mockMessages = [{ id: '1', role: 'user', content: 'hello', created_at: 'now' }];
    mockUseSWR.mockReturnValue({
      data: { thread: { id: 'test-id' }, messages: mockMessages },
      error: null,
      mutate: vi.fn(),
      isLoading: false
    });

    const { result } = renderHook(() => usePlanningThread('test-id'));

    expect(result.current.messages).toEqual(mockMessages);
  });
});

