import { useEffect, useRef, useCallback } from 'react';
import type { SimulationInput, SimNode, SimLink, SimulationOptions } from './types';
import { SimulationScheduler } from './scheduler';
import { computeCommunityCenters, computeConnectedComponents } from './fibonacci-cluster';

function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return hash;
}

const hasWorker = typeof Worker !== 'undefined';

export function useForceSimulation(
  input: SimulationInput | null,
  options: SimulationOptions = {}
) {
  const schedulerRef = useRef<SimulationScheduler | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const inputKeyRef = useRef('');
  const positionsRef = useRef<Float64Array>(new Float64Array(0));
  const nodesDataRef = useRef<SimNode[]>([]);
  const linksDataRef = useRef<SimLink[]>([]);
  const isRunningRef = useRef(false);
  const subscribersRef = useRef(new Set<() => void>());
  const pendingStepRef = useRef(false);

  useEffect(() => {
    if (hasWorker) {
      try {
        const workerUrl = new URL('./simulation.worker.ts', import.meta.url);
        const worker = new Worker(workerUrl, { type: 'module' });
        workerRef.current = worker;

        worker.onmessage = (e: MessageEvent) => {
          const { type: msgType, isRunning, positions } = e.data;
          if (msgType === 'step') {
            if (positions) {
              positionsRef.current = new Float64Array(positions);
              const pos = positionsRef.current;
              if (pos.length >= nodesDataRef.current.length * 3) {
                for (let i = 0; i < nodesDataRef.current.length; i++) {
                  const idx = i * 3;
                  nodesDataRef.current[i].x = pos[idx];
                  nodesDataRef.current[i].y = pos[idx + 1];
                  nodesDataRef.current[i].z = pos[idx + 2];
                }
              }
            }
            isRunningRef.current = isRunning;
            pendingStepRef.current = false;
            for (const fn of subscribersRef.current) fn();
          }
        };

        return () => {
          worker.terminate();
          workerRef.current = null;
        };
      } catch {
        workerRef.current = null;
      }
    }

    if (!workerRef.current) {
      schedulerRef.current = new SimulationScheduler(options);
    }

    return () => {
      schedulerRef.current?.destroy();
      schedulerRef.current = null;
    };
  }, [options]);

  useEffect(() => {
    if (!input || input.nodes.length === 0) {
      nodesDataRef.current = [];
      linksDataRef.current = [];
      if (workerRef.current) {
        workerRef.current.postMessage({ type: 'stop' });
      }
      if (schedulerRef.current) {
        schedulerRef.current.stop();
      }
      inputKeyRef.current = '';
      return;
    }

    const key = `${input.nodes.length}:${input.links.length}`;
    if (key === inputKeyRef.current) return;
    inputKeyRef.current = key;

    nodesDataRef.current = input.nodes.map(n => ({ ...n }));
    linksDataRef.current = [...input.links];

    if (workerRef.current) {
      initWorker(workerRef.current, input, options, nodesDataRef);
      isRunningRef.current = true;
    } else if (schedulerRef.current) {
      schedulerRef.current.initialize(input);
      const simNodes = schedulerRef.current.getNodes();
      for (let i = 0; i < nodesDataRef.current.length; i++) {
        if (simNodes[i]) {
          nodesDataRef.current[i].x = simNodes[i].x;
          nodesDataRef.current[i].y = simNodes[i].y;
          nodesDataRef.current[i].z = simNodes[i].z;
          nodesDataRef.current[i].vx = simNodes[i].vx;
          nodesDataRef.current[i].vy = simNodes[i].vy;
          nodesDataRef.current[i].vz = simNodes[i].vz;
        }
      }
      isRunningRef.current = true;
    }
  }, [input, options]);

  const step = useCallback(() => {
    if (workerRef.current) {
      if (pendingStepRef.current) return;
      pendingStepRef.current = true;
      workerRef.current.postMessage({ type: 'step' });
    } else if (schedulerRef.current) {
      if (!schedulerRef.current.getIsRunning()) return;
      schedulerRef.current.step();
      const pos = schedulerRef.current.getNodes();
      for (let i = 0; i < nodesDataRef.current.length; i++) {
        if (pos[i]) {
          nodesDataRef.current[i].x = pos[i].x;
          nodesDataRef.current[i].y = pos[i].y;
          nodesDataRef.current[i].z = pos[i].z;
        }
      }
      isRunningRef.current = schedulerRef.current.getIsRunning();
      for (const fn of subscribersRef.current) fn();
    }
  }, []);

  const subscribe = useCallback((fn: () => void) => {
    subscribersRef.current.add(fn);
    return () => { subscribersRef.current.delete(fn); };
  }, []);

  const reheat = useCallback((alpha = 0.3) => {
    if (workerRef.current) {
      workerRef.current.postMessage({ type: 'reheat', data: { alpha } });
    } else if (schedulerRef.current) {
      schedulerRef.current.reheat(alpha);
    }
    isRunningRef.current = true;
  }, []);

  const pause = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.postMessage({ type: 'pause' });
    } else if (schedulerRef.current) {
      schedulerRef.current.pause();
    }
    isRunningRef.current = false;
  }, []);

  const resume = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.postMessage({ type: 'resume' });
    } else if (schedulerRef.current) {
      schedulerRef.current.resume();
    }
  }, []);

  const getPositions = useCallback((): { nodes: SimNode[]; links: SimLink[] } => ({
    nodes: nodesDataRef.current,
    links: linksDataRef.current,
  }), []);

  const getIsRunning = useCallback((): boolean => {
    if (schedulerRef.current) return schedulerRef.current.getIsRunning();
    return isRunningRef.current;
  }, []);

  return { step, subscribe, getPositions, reheat, pause, resume, getIsRunning };
}

interface NodeWithCommunity extends SimNode {
  community_id?: number;
}

function initWorker(
  worker: Worker,
  input: SimulationInput,
  options: SimulationOptions,
  nodesDataRef: React.MutableRefObject<SimNode[]>
) {
  const N = input.nodes.length;
  const E = input.links.length;
  const is2D = (options.dimension ?? '2d') === '2d';
  const boundary = 40 * Math.pow(N, 1 / 3) + 150;

  const hasCommunityIds = input.nodes.some((n): n is NodeWithCommunity => 'community_id' in n && n.community_id !== undefined);

  let clusterCentersX: Float64Array;
  let clusterCentersY: Float64Array;
  let clusterCentersZ: Float64Array;
  let nodeLabels: Int32Array;

  if (hasCommunityIds) {
    const communityIds = input.nodes.map(n => (n as NodeWithCommunity).community_id);
    const result = computeCommunityCenters(communityIds, boundary, is2D);
    clusterCentersX = result.centersX;
    clusterCentersY = result.centersY;
    clusterCentersZ = result.centersZ;
    nodeLabels = result.communityIndex;
  } else {
    const linksForComponents = input.links.map(l => ({
      source: typeof l.source === 'string' ? l.source : (l.source as SimNode).id,
      target: typeof l.target === 'string' ? l.target : (l.target as SimNode).id,
    }));
    const componentIds = computeConnectedComponents(
      input.nodes.map(n => n.id),
      linksForComponents
    );
    const result = computeCommunityCenters(componentIds, boundary, is2D);
    clusterCentersX = result.centersX;
    clusterCentersY = result.centersY;
    clusterCentersZ = result.centersZ;
    nodeLabels = result.communityIndex;
  }

  const clusterCount = clusterCentersX.length;

  const nodeMap = new Map(input.nodes.map((n, i) => [n.id, i]));

  const seed = hashString(input.nodes.map(n => n.id).sort().join(','));
  const rng = mulberry32(seed);

  const positions = new Float64Array(N * 3);
  const chargeArray = new Float64Array(N);
  const nodeDegrees = new Int32Array(N);

  for (let i = 0; i < N; i++) {
    const node = input.nodes[i];
    const ci = nodeLabels[i];
    const cx = ci >= 0 && ci < clusterCount ? clusterCentersX[ci] : 0;
    const cy = ci >= 0 && ci < clusterCount ? clusterCentersY[ci] : 0;
    const cz = is2D ? 0 : (ci >= 0 && ci < clusterCount ? clusterCentersZ[ci] : 0);
    const jitter = () => (rng() - 0.5) * 40;
    const px = node.x ?? cx + jitter();
    const py = node.y ?? cy + jitter();
    const pz = is2D ? 0 : (node.z ?? cz + jitter());

    positions[i * 3] = isNaN(px) ? jitter() : px;
    positions[i * 3 + 1] = isNaN(py) ? jitter() : py;
    positions[i * 3 + 2] = isNaN(pz) ? 0 : pz;

    const roleScale = node.roleScale ?? 1.0;
    const degree = node.degree ?? 0;
    nodeDegrees[i] = degree;
    const raw = -120 * roleScale * (1 + 0.5 * Math.log2(degree + 1));
    chargeArray[i] = Math.max(raw, -1500);
  }

  for (let i = 0; i < N; i++) {
    if (nodesDataRef.current[i]) {
      nodesDataRef.current[i].x = positions[i * 3];
      nodesDataRef.current[i].y = positions[i * 3 + 1];
      nodesDataRef.current[i].z = positions[i * 3 + 2];
    }
  }

  const linkSources = new Int32Array(E);
  const linkTargets = new Int32Array(E);
  const linkWeights = new Float64Array(E);

  for (let i = 0; i < E; i++) {
    const link = input.links[i];
    const srcId = typeof link.source === 'string' ? link.source : (link.source as SimNode).id;
    const tgtId = typeof link.target === 'string' ? link.target : (link.target as SimNode).id;
    const srcIdx = nodeMap.get(srcId) ?? 0;
    const tgtIdx = nodeMap.get(tgtId) ?? 0;
    linkSources[i] = srcIdx;
    linkTargets[i] = tgtIdx;

    const srcDeg = input.nodes[srcIdx]?.degree ?? 1;
    const tgtDeg = input.nodes[tgtIdx]?.degree ?? 1;
    linkWeights[i] = 1 / Math.sqrt(1 + Math.min(srcDeg, tgtDeg));
  }

  positionsRef.current = positions;

    worker.postMessage({
      type: 'init',
      data: {
        nodeCount: N,
        linkCount: E,
        clusterCount,
        boundary,
        alphaDecay: options.alphaDecay ?? 0.012,
        alphaMin: options.alphaMin ?? 0.005,
        chargeStrength: options.chargeStrength ?? -300,
        linkDistance: options.linkDistance ?? 100,
        dimension: options.dimension ?? '3d',
      positions: positions.buffer,
      linkSources: linkSources.buffer,
      linkTargets: linkTargets.buffer,
      linkWeights: linkWeights.buffer,
      clusterCentersX: clusterCentersX.buffer,
      clusterCentersY: clusterCentersY.buffer,
      clusterCentersZ: clusterCentersZ.buffer,
      nodeLabels: nodeLabels.buffer,
      chargeArray: chargeArray.buffer,
      nodeDegrees: nodeDegrees.buffer,
    },
  }, [
    positions.buffer,
    linkSources.buffer,
    linkTargets.buffer,
    linkWeights.buffer,
    clusterCentersX.buffer,
    clusterCentersY.buffer,
    clusterCentersZ.buffer,
    nodeLabels.buffer,
    chargeArray.buffer,
    nodeDegrees.buffer,
  ]);
}

const positionsRef = { current: new Float64Array(0) };

export type { SimNode, SimLink, SimulationInput, SimulationOptions } from './types';
