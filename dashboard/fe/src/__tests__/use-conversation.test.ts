import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useConversation } from '../hooks/use-conversation';
import useSWR from 'swr';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

describe('use-conversation hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return default state when no id is provided', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const result = useConversation();
    expect(result.conversation).toBeUndefined();
    expect(result.isLoading).toBe(false);
    expect(result.isError).toBeUndefined();
    expect(useSWR).toHaveBeenCalledWith(null, expect.any(Function));
  });

  it('should construct correct SWR key with id', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    useConversation('conv-123');
    expect(useSWR).toHaveBeenCalledWith('/conversations/conv-123', expect.any(Function));
  });

  it('should return conversation data when loaded', () => {
    const mockConversation = {
      id: 'conv-123',
      title: 'Test Conversation',
      created_at: '2024-01-01',
      last_activity_at: '2024-01-02',
      messages: [
        { id: 'msg-1', role: 'user', content: 'Hello', created_at: '2024-01-01' },
      ],
    };
    (useSWR as any).mockReturnValue({
      data: mockConversation,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const result = useConversation('conv-123');
    expect(result.conversation).toEqual(mockConversation);
    expect(result.isLoading).toBe(false);
  });

  it('should return isLoading true while fetching', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: vi.fn(),
    });

    const result = useConversation('conv-123');
    expect(result.isLoading).toBe(true);
  });

  it('should return isError when fetch fails', () => {
    const mockError = new Error('Network error');
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: mockError,
      isLoading: false,
      mutate: vi.fn(),
    });

    const result = useConversation('conv-123');
    expect(result.isError).toBe(mockError);
  });

  it('should expose sendMessage, rename, remove and mutate functions', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const result = useConversation('conv-123');
    expect(typeof result.sendMessage).toBe('function');
    expect(typeof result.rename).toBe('function');
    expect(typeof result.remove).toBe('function');
    expect(typeof result.mutate).toBe('function');
  });

  it('sendMessage is a stub (no-op) pending streaming implementation', async () => {
    // NOTE: sendMessage in use-conversation.ts is intentionally a no-op stub.
    // The comment in the source reads: "for streaming we usually handle it
    // outside or rely on WS." This test documents that the function exists
    // but does not perform any API call. When streaming is implemented,
    // this test should be updated to verify actual behavior.
    const { apiPost } = await import('@/lib/api-client');
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const result = useConversation('conv-123');
    await result.sendMessage('hello');
    // sendMessage is a no-op, so apiPost should NOT have been called
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('rename calls apiPatch with correct path and title', async () => {
    const { apiPatch } = await import('@/lib/api-client');
    const mockMutate = vi.fn();
    (useSWR as any).mockReturnValue({
      data: { id: 'conv-123', title: 'Old Title', messages: [] },
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    const result = useConversation('conv-123');
    await result.rename('New Title');
    expect(apiPatch).toHaveBeenCalledWith('/conversations/conv-123', { title: 'New Title' });
    expect(mockMutate).toHaveBeenCalled();
  });

  it('remove calls apiDelete with correct path', async () => {
    const { apiDelete } = await import('@/lib/api-client');
    const mockMutate = vi.fn();
    (useSWR as any).mockReturnValue({
      data: { id: 'conv-123', title: 'To Delete', messages: [] },
      error: undefined,
      isLoading: false,
      mutate: mockMutate,
    });

    const result = useConversation('conv-123');
    await result.remove();
    expect(apiDelete).toHaveBeenCalledWith('/conversations/conv-123');
    expect(mockMutate).toHaveBeenCalled();
  });
});
