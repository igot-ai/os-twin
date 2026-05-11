import type { SimNode, SimLink, SimulationInput, SimulationOptions } from './types';
import { computeCommunityCenters, computeConnectedComponents } from './fibonacci-cluster';
import {
  applyClusterAttraction,
  applyLinkForce,
  applyRepulsionForce,
  applyBoundary,
  applyCenterGravity,
  integratePositions,
} from './forces';

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

interface NodeWithCommunity extends SimNode {
  community_id?: number;
}

export class SimulationScheduler {
  private nodes: SimNode[] = [];
  private links: SimLink[] = [];
  private clusterCenters = new Map<string, { x: number; y: number; z: number }>();
  private boundary = 0;
  private alpha = 1;
  private isRunning = false;
  private is2D = true;

  private chargeStrength = -400;
  private linkDistance = 80;
  private alphaDecay = 0.008;
  private alphaMin = 0.005;
  private stepCount = 0;

  constructor(options: SimulationOptions = {}) {
    this.chargeStrength = options.chargeStrength ?? -300;
    this.linkDistance = options.linkDistance ?? 100;
    this.alphaDecay = options.alphaDecay ?? 0.012;
    this.alphaMin = options.alphaMin ?? 0.005;
    this.is2D = (options.dimension ?? '2d') === '2d';
  }

  initialize(input: SimulationInput): void {
    this.stop();

    const { nodes: inputNodes, links: inputLinks } = input;
    const N = inputNodes.length;

    this.boundary = 40 * Math.pow(N, 1 / 3) + 150;
    this.is2D = true;
    this.stepCount = 0;

    const hasCommunityIds = inputNodes.some((n): n is NodeWithCommunity => 'community_id' in n && n.community_id !== undefined);

    const computeCommunityKeys = (): string[] => {
      if (hasCommunityIds) {
        return inputNodes.map(n => String((n as NodeWithCommunity).community_id ?? -1));
      }
      const linksForComp = inputLinks.map(l => ({
        source: typeof l.source === 'string' ? l.source : (l.source as SimNode).id,
        target: typeof l.target === 'string' ? l.target : (l.target as SimNode).id,
      }));
      const cids = computeConnectedComponents(inputNodes.map(n => n.id), linksForComp);
      return cids.map(String);
    };

    const communityKeys = computeCommunityKeys();

    const communityIds = hasCommunityIds
      ? inputNodes.map(n => (n as NodeWithCommunity).community_id)
      : communityKeys.map(k => Number(k));

    const result = computeCommunityCenters(communityIds, this.boundary, this.is2D);
    const communityClusterCenters = new Map<string, { x: number; y: number; z: number }>();
    for (let i = 0; i < result.uniqueCommunities.length; i++) {
      communityClusterCenters.set(String(result.uniqueCommunities[i]), {
        x: result.centersX[i],
        y: result.centersY[i],
        z: result.centersZ[i],
      });
    }
    this.clusterCenters = communityClusterCenters;

    const prevPositions = new Map<string, { x: number; y: number; z: number; vx: number; vy: number; vz: number }>();
    for (const n of this.nodes) {
      if (n.x != null && n.y != null && n.z != null) {
        prevPositions.set(n.id, { x: n.x, y: n.y, z: n.z, vx: n.vx ?? 0, vy: n.vy ?? 0, vz: n.vz ?? 0 });
      }
    }

    const seed = hashString(inputNodes.map(n => n.id).sort().join(','));
    const rng = mulberry32(seed);

    this.nodes = inputNodes.map((n, i) => {
      const prev = prevPositions.get(n.id);
      const center = this.clusterCenters.get(communityKeys[i]) ?? { x: 0, y: 0, z: 0 };
      const jitter = () => (rng() - 0.5) * 40;
      return {
        ...n,
        x: prev?.x ?? center.x + jitter(),
        y: prev?.y ?? center.y + jitter(),
        z: prev?.z ?? (this.is2D ? 0 : center.z + jitter()),
        vx: prev?.vx ?? 0,
        vy: prev?.vy ?? 0,
        vz: prev?.vz ?? (this.is2D ? 0 : 0),
      };
    });

    const nodeMap = new Map(this.nodes.map(n => [n.id, n]));
    this.links = inputLinks
      .map(l => {
        const sourceNode = typeof l.source === 'string' ? nodeMap.get(l.source) : nodeMap.get((l.source as SimNode).id);
        const targetNode = typeof l.target === 'string' ? nodeMap.get(l.target) : nodeMap.get((l.target as SimNode).id);
        if (!sourceNode || !targetNode) return null;
        return { ...l, source: sourceNode, target: targetNode } as SimLink;
      })
      .filter((l): l is NonNullable<typeof l> => l !== null);

    this.alpha = 0.8;
    this.isRunning = true;
  }

  reheat(alpha: number = 0.3): void {
    this.alpha = alpha;
    if (!this.isRunning) {
      this.start();
    }
  }

  pause(): void {
    if (this.isRunning) {
      this.stop();
    }
  }

  resume(): void {
    if (!this.isRunning && this.alpha > this.alphaMin) {
      this.start();
    }
  }

  step(): void {
    if (!this.isRunning) return;

    this.stepCount++;

    applyClusterAttraction(this.nodes, this.clusterCenters, this.alpha);
    applyLinkForce(this.links, this.linkDistance, this.alpha);
    applyRepulsionForce(this.nodes, this.chargeStrength, this.alpha);
    applyBoundary(this.nodes, this.boundary, this.alpha, this.is2D);
    applyCenterGravity(this.nodes, this.alpha, this.is2D);
    integratePositions(this.nodes, 0.88, this.is2D);

    this.alpha -= this.alphaDecay * this.alpha;

    if (this.alpha <= this.alphaMin) {
      this.isRunning = false;
    }
  }

  start(): void {
    this.isRunning = true;
  }

  stop(): void {
    this.isRunning = false;
  }

  getNodes(): SimNode[] {
    return this.nodes;
  }

  getLinks(): SimLink[] {
    return this.links;
  }

  getIsRunning(): boolean {
    return this.isRunning;
  }

  destroy(): void {
    this.stop();
  }
}
