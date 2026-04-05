import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useFileTree, useFileList, useFileContent, useFileChanges } from '../hooks/use-files';
import useSWR from 'swr';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

describe('use-files hooks', () => {
  const planId = 'plan-001';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useFileTree', () => {
    it('should return tree data', () => {
      const mockTree = [{ name: 'src', type: 'directory', path: 'src', children: [] }];
      (useSWR as any).mockReturnValue({
        data: mockTree,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { tree } = useFileTree(planId);
      expect(tree).toEqual(mockTree);
      expect(useSWR).toHaveBeenCalledWith(`/plans/${planId}/files/tree`);
    });
  });

  describe('useFileList', () => {
    it('should return file list for a path', () => {
      const path = 'src';
      const mockEntries = [{ name: 'main.py', type: 'file', size: 100 }];
      (useSWR as any).mockReturnValue({
        data: mockEntries,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { entries } = useFileList(planId, path);
      expect(entries).toEqual(mockEntries);
      expect(useSWR).toHaveBeenCalledWith(`/plans/${planId}/files?path=${encodeURIComponent(path)}`);
    });
  });

  describe('useFileContent', () => {
    it('should return file content', () => {
      const path = 'src/main.py';
      const mockContent = { path, content: 'print("hello")', encoding: 'utf-8', size: 15, mime_type: 'text/x-python', truncated: false };
      (useSWR as any).mockReturnValue({
        data: mockContent,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { content } = useFileContent(planId, path);
      expect(content).toEqual(mockContent);
      expect(useSWR).toHaveBeenCalledWith(`/plans/${planId}/files/content?path=${encodeURIComponent(path)}`, expect.any(Object));
    });

    it('should return null if no path provided', () => {
      (useSWR as any).mockReturnValue({ data: undefined });
      useFileContent(planId, null);
      expect(useSWR).toHaveBeenCalledWith(null, expect.any(Object));
    });
  });

  describe('useFileChanges', () => {
    it('should return git changes', () => {
      const mockChanges = { git_enabled: true, status: ['M src/main.py'], recent_commits: [] };
      (useSWR as any).mockReturnValue({
        data: mockChanges,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { changes } = useFileChanges(planId);
      expect(changes).toEqual(mockChanges);
      expect(useSWR).toHaveBeenCalledWith(`/plans/${planId}/files/changes`, expect.any(Object));
    });
  });
});
