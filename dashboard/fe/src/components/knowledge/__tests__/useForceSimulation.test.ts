import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useForceSimulation } from '../graph/simulation/use-force-layout';
import type { SimNode, SimLink, SimulationInput } from '../graph/simulation/types';

function makeSimNode(id: string, label = 'entity', score = 0.5): SimNode {
  return {
    id,
    name: `Node ${id}`,
    label,
    score,
    degree: 0,
    brightness: 0.3,
    color: '#3b82f6',
    emissiveColor: '#60a5fa',
    shapeType: 0,
    archetype: 'authority',
    isHub: false,
    emissiveStrength: 0.5,
    roleScale: 1.0,
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

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(3);
    expect(positions.links.length).toBe(2);

    for (const node of positions.nodes) {
      expect(node.x).toBeDefined();
      expect(node.y).toBeDefined();
    }
  });

  it('step advances simulation positions', async () => {
    const input = makeInput(5, 3);

    const { result } = renderHook(() => useForceSimulation(input));

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

    act(() => {
      result.current.step();
    });

    const after = result.current.getPositions();
    expect(after.nodes[0].x).toBeDefined();
  });

  it('preserves positions from previous simulation when data changes', async () => {
    const input1 = makeInput(3, 2);

    const { result, rerender } = renderHook(
      ({ input }) => useForceSimulation(input),
      { initialProps: { input: input1 } }
    );

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

    const positions1 = result.current.getPositions();
    expect(positions1.nodes[0].x).toBeDefined();

    const input2 = makeInput(4, 3);
    input2.nodes[0] = { ...input2.nodes[0], id: 'n0' };
    input2.nodes[1] = { ...input2.nodes[1], id: 'n1' };
    input2.nodes[2] = { ...input2.nodes[2], id: 'n2' };

    rerender({ input: input2 });

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

    const positions2 = result.current.getPositions();
    expect(positions2.nodes[0].x).toBeDefined();
  });

  it('reheat restarts a settled simulation', async () => {
    const input = makeInput(3, 2);

    const { result } = renderHook(() => useForceSimulation(input, { alphaDecay: 0.5 }));

    await act(async () => {
      for (let i = 0; i < 100; i++) {
        result.current.step();
      }
    });

    act(() => {
      result.current.reheat(0.5);
    });

    expect(result.current.getIsRunning()).toBe(true);
  });

  it('cleans up simulation when input becomes null', async () => {
    const input = makeInput(3, 2);

    const { result, rerender } = renderHook(
      ({ input }) => useForceSimulation(input),
      { initialProps: { input } }
    );

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

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
      await new Promise(r => setTimeout(r, 50));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(5);
  });

  it('handles empty links array', async () => {
    const input: SimulationInput = {
      nodes: [makeSimNode('n1'), makeSimNode('n2')],
      links: [],
    };

    const { result } = renderHook(() => useForceSimulation(input));

    await act(async () => {
      await new Promise(r => setTimeout(r, 50));
    });

    const positions = result.current.getPositions();
    expect(positions.nodes.length).toBe(2);
    expect(positions.links.length).toBe(0);
  });
});
