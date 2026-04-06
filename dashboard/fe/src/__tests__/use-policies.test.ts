import { describe, it, expect, vi, beforeEach } from 'vitest';
import { usePolicies, usePolicy, usePolicyHistory } from '../hooks/use-policies';
import useSWR from 'swr';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

describe('use-policies hooks', () => {
  const roleId = 'role-001';
  const policyId = 'policy-001';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('usePolicies', () => {
    it('should return policies for a role', () => {
      const mockPolicies = [
        { policy_id: 'p1', name: 'Policy 1', trigger: { role_id: 'role-001' }, pipeline: [] },
        { policy_id: 'p2', name: 'Policy 2', trigger: { role_id: 'role-002' }, pipeline: [] }
      ];
      (useSWR as any).mockReturnValue({
        data: mockPolicies,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { policies } = usePolicies(roleId);
      expect(policies).toHaveLength(1);
      expect(policies?.[0].policy_id).toBe('p1');
      expect(useSWR).toHaveBeenCalledWith('/policies');
    });
  });

  describe('usePolicy', () => {
    it('should return a single policy', () => {
      const mockPolicy = { policy_id: policyId, name: 'Test Policy' };
      (useSWR as any).mockReturnValue({
        data: mockPolicy,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { policy } = usePolicy(policyId);
      expect(policy).toEqual(mockPolicy);
      expect(useSWR).toHaveBeenCalledWith(`/policies/${policyId}`);
    });
  });

  describe('usePolicyHistory', () => {
    it('should return policy history', () => {
      const mockHistory = [
        { policy_id: policyId, status: 'success', finished_at: '2026-01-01T00:00:00Z' }
      ];
      (useSWR as any).mockReturnValue({
        data: mockHistory,
        error: undefined,
        isLoading: false,
        mutate: vi.fn(),
      });

      const { history } = usePolicyHistory(policyId);
      expect(history).toEqual(mockHistory);
      expect(useSWR).toHaveBeenCalledWith(`/policies/${policyId}/history`);
    });
  });
});
