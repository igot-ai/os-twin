/**
 * Unit tests for the useAssetStaging hook.
 *
 * This hook provides the browser-side staging buffer for the web UI,
 * matching the same stage→flush pattern used by Discord and Telegram bots.
 *
 * File under test: dashboard/fe/src/hooks/use-asset-staging.ts
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAssetStaging } from '@/hooks/use-asset-staging';

// Mock api-client
vi.mock('@/lib/api-client', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}));

function createMockFile(name: string, size: number, type: string): File {
  const buffer = new ArrayBuffer(size);
  return new File([buffer], name, { type });
}

describe('useAssetStaging', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Initial state ───────────────────────────────────────────────

  it('starts with empty staged files', () => {
    const { result } = renderHook(() => useAssetStaging());

    expect(result.current.stagedFiles).toEqual([]);
    expect(result.current.stagedCount).toBe(0);
    expect(result.current.stagedSizeBytes).toBe(0);
    expect(result.current.isFlushing).toBe(false);
  });

  // ── stageFiles ─────────────────────────────────────────────────

  it('stages files and updates count/size', () => {
    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([
        createMockFile('a.png', 100, 'image/png'),
        createMockFile('b.jpg', 200, 'image/jpeg'),
      ]);
    });

    expect(result.current.stagedCount).toBe(2);
    expect(result.current.stagedSizeBytes).toBe(300);
    expect(result.current.stagedFiles[0].name).toBe('a.png');
    expect(result.current.stagedFiles[1].name).toBe('b.jpg');
  });

  it('accumulates files across multiple stageFiles calls', () => {
    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([createMockFile('a.png', 50, 'image/png')]);
    });
    act(() => {
      result.current.stageFiles([createMockFile('b.png', 75, 'image/png')]);
    });

    expect(result.current.stagedCount).toBe(2);
    expect(result.current.stagedSizeBytes).toBe(125);
  });

  it('rejects when total size exceeds MAX_SIZE', () => {
    const { result } = renderHook(() => useAssetStaging());
    const MAX_SIZE = 50 * 1024 * 1024; // 50MB

    act(() => {
      result.current.stageFiles([
        createMockFile('huge.mp4', MAX_SIZE + 1, 'video/mp4'),
      ]);
    });

    // File should be rejected
    expect(result.current.stagedCount).toBe(0);
    expect(result.current.lastError).toContain('exceeds');
  });

  it('preserves epicRef when provided', () => {
    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles(
        [createMockFile('spec.png', 100, 'image/png')],
        'EPIC-002',
      );
    });

    expect(result.current.stagedFiles[0].epicRef).toBe('EPIC-002');
  });

  // ── flushTo ─────────────────────────────────────────────────────

  it('flushTo uploads all staged files and clears buffer', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        assets: [{ filename: 's.png', original_name: 'a.png', uploaded_at: '2026-01-01' }],
      }),
    });
    global.fetch = mockFetch;

    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([createMockFile('a.png', 100, 'image/png')]);
    });

    await act(async () => {
      await result.current.flushTo('plan-abc');
    });

    expect(result.current.stagedCount).toBe(0);
    expect(mockFetch).toHaveBeenCalledOnce();

    // Verify the fetch was called with the correct plan endpoint
    const fetchUrl = mockFetch.mock.calls[0][0];
    expect(fetchUrl).toContain('/api/plans/plan-abc/assets');
  });

  it('flushTo is a no-op when no files are staged', async () => {
    const mockFetch = vi.fn();
    global.fetch = mockFetch;

    const { result } = renderHook(() => useAssetStaging());

    await act(async () => {
      await result.current.flushTo('plan-abc');
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('flushTo sets isFlushing during upload', async () => {
    let resolveFetch: Function;
    const fetchPromise = new Promise((resolve) => { resolveFetch = resolve; });
    global.fetch = vi.fn().mockReturnValue(fetchPromise);

    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([createMockFile('a.png', 100, 'image/png')]);
    });

    // Start flush but don't await
    let flushPromise: Promise<any>;
    act(() => {
      flushPromise = result.current.flushTo('plan-abc');
    });

    expect(result.current.isFlushing).toBe(true);

    // Resolve the fetch
    await act(async () => {
      resolveFetch!({
        ok: true,
        json: async () => ({ assets: [] }),
      });
      await flushPromise!;
    });

    expect(result.current.isFlushing).toBe(false);
  });

  // ── clearStaged ─────────────────────────────────────────────────

  it('clearStaged removes all staged files', () => {
    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([
        createMockFile('a.png', 100, 'image/png'),
        createMockFile('b.jpg', 200, 'image/jpeg'),
      ]);
    });
    expect(result.current.stagedCount).toBe(2);

    act(() => {
      result.current.clearStaged();
    });

    expect(result.current.stagedCount).toBe(0);
    expect(result.current.stagedSizeBytes).toBe(0);
    expect(result.current.stagedFiles).toEqual([]);
  });

  // ── removeStaged ────────────────────────────────────────────────

  it('removeStaged removes a specific file by index', () => {
    const { result } = renderHook(() => useAssetStaging());

    act(() => {
      result.current.stageFiles([
        createMockFile('a.png', 100, 'image/png'),
        createMockFile('b.jpg', 200, 'image/jpeg'),
        createMockFile('c.gif', 50, 'image/gif'),
      ]);
    });

    act(() => {
      result.current.removeStaged(1); // remove b.jpg
    });

    expect(result.current.stagedCount).toBe(2);
    expect(result.current.stagedFiles[0].name).toBe('a.png');
    expect(result.current.stagedFiles[1].name).toBe('c.gif');
  });

  // ── hasStagedFiles ──────────────────────────────────────────────

  it('hasStagedFiles reflects staging state', () => {
    const { result } = renderHook(() => useAssetStaging());

    expect(result.current.hasStagedFiles).toBe(false);

    act(() => {
      result.current.stageFiles([createMockFile('a.png', 100, 'image/png')]);
    });

    expect(result.current.hasStagedFiles).toBe(true);

    act(() => {
      result.current.clearStaged();
    });

    expect(result.current.hasStagedFiles).toBe(false);
  });
});
