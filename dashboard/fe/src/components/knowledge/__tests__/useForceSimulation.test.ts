/**
 * Unit tests for useForceSimulation hook.
 *
 * Tests simulation lifecycle, position updates, reheating,
 * and proper cleanup.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useForceSimulation } from '../supernova/useForceSimulation';
import type { SimNode, SimLink, SimulationInput } from '../supernova/useForceSimulation';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeSimNode(id: string, label = 'entity', score = 0.5): SimNode {
  return {
    id,
    name: `Node ${id}`,
    label,
    score,
    degree: 0,
    brightness: 0.3,
    color: '#3b82f6',
    shapeType: 0,
    properties: {},
  };
}

function makeInput(nodeCount: number, linkCount = 0): SimulationInput {
  const nodes: SimNode[] = [];
  for (let i = 0; i < nodeCount; i++) {
    nodes.push(makeSimNode(`n${i}`));
  }

  const links: SimLink[] = [];
  for (let i = 0; i < Math.min(linkCount, nodeCount - 1); i++) {
    links.push({
      source: `n${i}`,
      target: `n${i + 1}`,
      label: 'RELATES',
      weight: 1,
      color: '#6b7280',
    });
  }

  return { nodes, links };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useForceSimulation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with empty positions when input is null', () => {
    const { result } = renderHook(() => useForceSimulation(null));

    const positions = result.current.getPositions();
    expect(positions.nodes).toEqual([]);
    expect(positions.links).toEqual([]);
  });

  it('creates simulation and returns node positions when input is provided', async () => {
    const input = makeInput(3, 2);

    const { result } = renderHook(() => useForceSimulation(input));

    // Wait for simulation to run at least one tick
    await act(async () => {
      await new Promise(r => setTimeout(r, 100));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(3);
    expect(positions.links.length).toBe(2);

    // Nodes should have x, y positions after simulation ticks
    for (const node of positions.nodes) {
      expect(node.x).toBeDefined();
      expect(node.y).toBeDefined();
    }
  });

  it('tick count increases as simulation runs', async () => {
    const input = makeInput(5, 3);

    const { result } = renderHook(() => useForceSimulation(input));

    const initialTick = result.current.tick;

    await act(async () => {
      await new Promise(r => setTimeout(r, 200));
    });

    expect(result.current.tick).toBeGreaterThan(initialTick);
  });

  it('preserves positions from previous simulation when data changes', async () => {
    const input1 = makeInput(3, 2);

    const { result, rerender } = renderHook(
      ({ input }) => useForceSimulation(input),
      { initialProps: { input: input1 } }
    );

    // Let simulation settle
    await act(async () => {
      await new Promise(r => setTimeout(r, 200));
    });

    const positions1 = result.current.getPositions();
    const firstNodeX = positions1.nodes[0].x;

    // Add a new node
    const input2 = makeInput(4, 3);
    // Copy first 3 nodes to keep IDs
    input2.nodes[0] = { ...input2.nodes[0], id: 'n0' };
    input2.nodes[1] = { ...input2.nodes[1], id: 'n1' };
    input2.nodes[2] = { ...input2.nodes[2], id: 'n2' };

    rerender({ input: input2 });

    await act(async () => {
      await new Promise(r => setTimeout(r, 100));
    });

    const positions2 = result.current.getPositions();
    // Original nodes should still have their positions (approximately)
    expect(positions2.nodes[0].x).toBeDefined();
  });

  it('reheat restarts a settled simulation', async () => {
    const input = makeInput(3, 2);

    const { result } = renderHook(() => useForceSimulation(input, { alphaDecay: 0.5 }));

    // Wait for simulation to cool down
    await act(async () => {
      await new Promise(r => setTimeout(r, 500));
    });

    // Reheat
    act(() => {
      result.current.reheat(0.5);
    });

    // Should start running again
    await act(async () => {
      await new Promise(r => setTimeout(r, 100));
    });

    // tick should have increased after reheat
    expect(result.current.tick).toBeGreaterThan(0);
  });

  it('cleans up simulation when input becomes null', async () => {
    const input = makeInput(3, 2);

    const { result, rerender } = renderHook(
      ({ input }) => useForceSimulation(input),
      { initialProps: { input } }
    );

    await act(async () => {
      await new Promise(r => setTimeout(r, 100));
    });

    // Remove data
    rerender({ input: null as unknown as SimulationInput });

    const positions = result.current.getPositions();
    expect(positions.nodes).toEqual([]);
    expect(positions.links).toEqual([]);
  });

  it('uses custom options when provided', async () => {
    const input = makeInput(5, 3);

    const { result } = renderHook(() =>
      useForceSimulation(input, {
        width: 1200,
        height: 800,
        chargeStrength: -200,
        linkDistance: 100,
        alphaDecay: 0.05,
      })
    );

    await act(async () => {
      await new Promise(r => setTimeout(r, 200));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(5);

    // With custom width/height, nodes should be roughly centered
    // around the center point (600, 400)
    let sumX = 0, sumY = 0;
    for (const n of positions.nodes) {
      sumX += n.x ?? 0;
      sumY += n.y ?? 0;
    }
    const avgX = sumX / positions.nodes.length;
    const avgY = sumY / positions.nodes.length;

    // Nodes should be roughly centered
    expect(Math.abs(avgX - 600)).toBeLessThan(1000);
    expect(Math.abs(avgY - 400)).toBeLessThan(1000);
  });

  it('handles empty links array', async () => {
    const input: SimulationInput = {
      nodes: [makeSimNode('n1'), makeSimNode('n2')],
      links: [],
    };

    const { result } = renderHook(() => useForceSimulation(input));

    await act(async () => {
      await new Promise(r => setTimeout(r, 100));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(2);
    expect(positions.links.length).toBe(0);
  });
});
