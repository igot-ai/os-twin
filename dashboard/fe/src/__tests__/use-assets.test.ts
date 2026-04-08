import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAssets } from '../hooks/use-assets';
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

describe('use-assets hook', () => {
  const planId = 'plan-001';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return assets from SWR data', () => {
    const mockAssets = [
      { filename: 'logo.png', original_name: 'logo.png', mime_type: 'image/png', uploaded_at: '2024-01-01' },
    ];
    (useSWR as any).mockReturnValue({
      data: { plan_id: planId, assets: mockAssets, count: 1 },
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useAssets(planId));
    expect(result.current.assets).toEqual(mockAssets);
    expect(result.current.count).toBe(1);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBeUndefined();
  });

  it('should construct the correct SWR key', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: vi.fn(),
    });

    renderHook(() => useAssets(planId));
    expect(useSWR).toHaveBeenCalledWith(
      `/plans/${planId}/assets`,
      expect.any(Function),
      expect.objectContaining({ refreshInterval: 10000 })
    );
  });

  it('should pass null key when planId is empty', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    renderHook(() => useAssets(''));
    expect(useSWR).toHaveBeenCalledWith(
      null,
      expect.any(Function),
      expect.any(Object)
    );
  });

  it('should return empty assets when data is undefined', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useAssets(planId));
    expect(result.current.assets).toEqual([]);
    expect(result.current.count).toBe(0);
  });

  it('should expose upload, bind, unbind, updateMeta and refresh functions', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useAssets(planId));
    expect(typeof result.current.uploadAssets).toBe('function');
    expect(typeof result.current.bindAsset).toBe('function');
    expect(typeof result.current.unbindAsset).toBe('function');
    expect(typeof result.current.updateAssetMeta).toBe('function');
    expect(typeof result.current.refresh).toBe('function');
  });

  it('should return uploading as false initially', () => {
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useAssets(planId));
    expect(result.current.uploading).toBe(false);
  });

  it('should return isError when SWR has an error', () => {
    const mockError = new Error('fetch failed');
    (useSWR as any).mockReturnValue({
      data: undefined,
      error: mockError,
      isLoading: false,
      mutate: vi.fn(),
    });

    const { result } = renderHook(() => useAssets(planId));
    expect(result.current.isError).toBe(mockError);
  });
});
