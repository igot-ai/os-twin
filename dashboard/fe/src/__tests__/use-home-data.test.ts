import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useHomeData } from '../hooks/use-home-data';
import useSWR from 'swr';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiGet: vi.fn(),
}));

describe('use-home-data hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should call SWR with /home endpoint', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
    });

    useHomeData();
    expect(useSWR).toHaveBeenCalledWith('/home', expect.any(Function), expect.objectContaining({
      fallbackData: expect.any(Object),
    }));
  });

  it('should return suggestions from data', () => {
    const mockData = {
      user: { name: 'Test', workspace: 'TestSpace' },
      categories: [],
      suggestions: [
        { id: 's1', text: 'Build something', icon: 'code' },
        { id: 's2', text: 'Deploy something', icon: 'deploy' },
      ],
    };
    (useSWR as any).mockReturnValue({
      data: mockData,
      error: undefined,
      isLoading: false,
    });

    const result = useHomeData();
    expect(result.data.suggestions).toHaveLength(2);
    expect(result.data.suggestions[0].text).toBe('Build something');
  });

  it('should return categories from data', () => {
    const mockData = {
      user: { name: 'Test', workspace: 'TestSpace' },
      categories: [
        { id: 'web', name: 'Web App', icon: 'web', description: 'Create a web app' },
      ],
      suggestions: [],
    };
    (useSWR as any).mockReturnValue({
      data: mockData,
      error: undefined,
      isLoading: false,
    });

    const result = useHomeData();
    expect(result.data.categories).toHaveLength(1);
    expect(result.data.categories[0].name).toBe('Web App');
  });

  it('should return loading state', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
    });

    const result = useHomeData();
    expect(result.isLoading).toBe(true);
  });

  it('should return error state', () => {
    const mockError = new Error('API error');
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: mockError,
      isLoading: false,
    });

    const result = useHomeData();
    expect(result.isError).toBe(mockError);
  });

  it('should fallback to mock data when data is undefined', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
    });

    const result = useHomeData();
    // Should return the hardcoded mockHomeData fallback
    expect(result.data).toBeDefined();
    expect(result.data.user.name).toBe('Alex');
    expect(result.data.suggestions.length).toBeGreaterThan(0);
    expect(result.data.categories.length).toBeGreaterThan(0);
  });
});
