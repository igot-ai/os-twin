/**
 * useForceSimulation — 3D Force Simulation for "Universe of Data" layout.
 *
 * Nodes form label-based "constellations" on a Fibonacci sphere surface.
 * Each label type gets a cluster center distributed evenly on the sphere,
 * and nodes are attracted toward their label's constellation.
 *
 * Forces:
 * 1. Label-cluster attraction — pull toward label center on sphere
 * 2. Sphere shell — constrain to sphere surface
 * 3. Spatial-hash repulsion — O(N) short-range repulsion via grid cells
 * 4. Link springs — connected nodes attract
 * 5. Center gravity — gentle pull to prevent drift
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SimNode {
  id: string;
  name: string;
  label: string;
  score: number;
  degree: number;
  brightness: number;
  color: string;
  shapeType: number;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

export interface SimLink {
  source: SimNode | string;
  target: SimNode | string;
  label: string;
  weight: number;
  color: string;
}

export interface SimulationInput {
  nodes: SimNode[];
  links: SimLink[];
}

// ---------------------------------------------------------------------------
// Fibonacci sphere — distribute N points evenly on sphere surface
// ---------------------------------------------------------------------------

function fibonacciSphere(count: number, radius: number): { x: number; y: number; z: number }[] {
  const points: { x: number; y: number; z: number }[] = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(count - 1, 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = goldenAngle * i;
    points.push({
      x: Math.cos(theta) * r * radius,
      y: y * radius,
      z: Math.sin(theta) * r * radius,
    });
  }
  return points;
}

// ---------------------------------------------------------------------------
// Spatial hash grid — O(N) repulsion
// ---------------------------------------------------------------------------

const CELL_SIZE = 40;

function hashKey(x: number, y: number, z: number): string {
  return `${Math.floor(x / CELL_SIZE)},${Math.floor(y / CELL_SIZE)},${Math.floor(z / CELL_SIZE)}`;
}

function buildGrid(nodes: SimNode[]): Map<string, number[]> {
  const grid = new Map<string, number[]>();
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const key = hashKey(n.x ?? 0, n.y ?? 0, n.z ?? 0);
    let cell = grid.get(key);
    if (!cell) {
      cell = [];
      grid.set(key, cell);
    }
    cell.push(i);
  }
  return grid;
}

const NEIGHBOR_OFFSETS = [-1, 0, 1];

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseForceSimulationOptions {
  width?: number;
  height?: number;
  chargeStrength?: number;
  linkDistance?: number;
  alphaDecay?: number;
  alphaMin?: number;
}

export function useForceSimulation(
  input: SimulationInput | null,
  options: UseForceSimulationOptions = {}
) {
  const {
    chargeStrength = -200,
    linkDistance = 60,
    alphaDecay = 0.015,
    alphaMin = 0.004,
  } = options;

  const rafRef = useRef<number | null>(null);
  const [tick, setTick] = useState(0);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const isRunningRef = useRef(false);
  const alphaRef = useRef(1);
  const loopFnRef = useRef<(() => void) | null>(null);

  const inputRef = useRef(input);
  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  useEffect(() => {
    if (!input || input.nodes.length === 0) {
      nodesRef.current = [];
      linksRef.current = [];
      requestAnimationFrame(() => setTick(t => t + 1));
      return;
    }

    const { nodes: inputNodes, links: inputLinks } = input;

    // ---- Compute label cluster centers on Fibonacci sphere ----
    const uniqueLabels = [...new Set(inputNodes.map(n => n.label))].sort();
    const N = inputNodes.length;
    // Sphere radius scales with cube root of node count (volume-proportional)
    const sphereRadius = 25 * Math.pow(N, 1 / 3) + 60;
    const clusterCenters = new Map<string, { x: number; y: number; z: number }>();
    const fibPoints = fibonacciSphere(uniqueLabels.length, sphereRadius);
    uniqueLabels.forEach((label, i) => {
      clusterCenters.set(label, fibPoints[i]);
    });

    // ---- Preserve previous positions ----
    const prevPositions = new Map<string, { x: number; y: number; z: number; vx: number; vy: number; vz: number }>();
    for (const n of nodesRef.current) {
      if (n.x != null && n.y != null && n.z != null) {
        prevPositions.set(n.id, { x: n.x, y: n.y, z: n.z, vx: n.vx ?? 0, vy: n.vy ?? 0, vz: n.vz ?? 0 });
      }
    }

    // ---- Initialize nodes near their label's cluster center ----
    const nodes: SimNode[] = inputNodes.map(n => {
      const prev = prevPositions.get(n.id);
      const center = clusterCenters.get(n.label) ?? { x: 0, y: 0, z: 0 };
      // Scatter around cluster center (±15 units jitter)
      const jitter = () => (Math.random() - 0.5) * 30;
      return {
        ...n,
        x: prev?.x ?? center.x + jitter(),
        y: prev?.y ?? center.y + jitter(),
        z: prev?.z ?? center.z + jitter(),
        vx: prev?.vx ?? 0,
        vy: prev?.vy ?? 0,
        vz: prev?.vz ?? 0,
      };
    });

    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    const links: SimLink[] = inputLinks
      .map(l => {
        const sourceNode = typeof l.source === 'string' ? nodeMap.get(l.source) : nodeMap.get((l.source as SimNode).id);
        const targetNode = typeof l.target === 'string' ? nodeMap.get(l.target) : nodeMap.get((l.target as SimNode).id);
        if (!sourceNode || !targetNode) return null;
        return { ...l, source: sourceNode, target: targetNode } as SimLink;
      })
      .filter((l): l is NonNullable<typeof l> => l !== null);

    nodesRef.current = nodes;
    linksRef.current = links;
    alphaRef.current = 1;
    isRunningRef.current = true;

    let frameCount = 0;

    const loop = () => {
      if (!isRunningRef.current) return;

      const alpha = alphaRef.current;
      const n = nodesRef.current;
      const l = linksRef.current;

      // 1. Label-cluster attraction — pull toward cluster center
      for (const node of n) {
        const center = clusterCenters.get(node.label);
        if (!center) continue;
        const dx = center.x - (node.x ?? 0);
        const dy = center.y - (node.y ?? 0);
        const dz = center.z - (node.z ?? 0);
        // Stronger pull for higher-score nodes (they anchor the cluster)
        const strength = 0.015 * alpha * (1 + node.score * 0.5);
        node.vx = (node.vx ?? 0) + dx * strength;
        node.vy = (node.vy ?? 0) + dy * strength;
        node.vz = (node.vz ?? 0) + dz * strength;
      }

      // 2. Link force (springs) — weaker than cluster to not override layout
      for (const link of l) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        const dx = (target.x ?? 0) - (source.x ?? 0);
        const dy = (target.y ?? 0) - (source.y ?? 0);
        const dz = (target.z ?? 0) - (source.z ?? 0);
        let dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist === 0) dist = 0.01;

        const strength = Math.min(1 / Math.max(source.degree, target.degree, 1), 0.3) * alpha * 0.5;
        const force = (dist - linkDistance) * strength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        const fz = (dz / dist) * force;

        source.vx = (source.vx ?? 0) + fx;
        source.vy = (source.vy ?? 0) + fy;
        source.vz = (source.vz ?? 0) + fz;
        target.vx = (target.vx ?? 0) - fx;
        target.vy = (target.vy ?? 0) - fy;
        target.vz = (target.vz ?? 0) - fz;
      }

      // 3. Repulsion via spatial hash grid — O(N) instead of O(N²)
      const grid = buildGrid(n);
      for (let i = 0; i < n.length; i++) {
        const a = n[i];
        const ax = a.x ?? 0, ay = a.y ?? 0, az = a.z ?? 0;
        const cx = Math.floor(ax / CELL_SIZE);
        const cy = Math.floor(ay / CELL_SIZE);
        const cz = Math.floor(az / CELL_SIZE);

        for (const ox of NEIGHBOR_OFFSETS) {
          for (const oy of NEIGHBOR_OFFSETS) {
            for (const oz of NEIGHBOR_OFFSETS) {
              const key = `${cx + ox},${cy + oy},${cz + oz}`;
              const cell = grid.get(key);
              if (!cell) continue;
              for (const j of cell) {
                if (j <= i) continue;
                const b = n[j];
                let dx = (b.x ?? 0) - ax;
                let dy = (b.y ?? 0) - ay;
                let dz = (b.z ?? 0) - az;
                let distSq = dx * dx + dy * dy + dz * dz;
                if (distSq === 0) {
                  dx = (Math.random() - 0.5);
                  dy = (Math.random() - 0.5);
                  dz = (Math.random() - 0.5);
                  distSq = dx * dx + dy * dy + dz * dz;
                }
                if (distSq < CELL_SIZE * CELL_SIZE * 4) {
                  const dist = Math.sqrt(distSq);
                  const force = (chargeStrength * alpha) / distSq;
                  const fx = (dx / dist) * force;
                  const fy = (dy / dist) * force;
                  const fz = (dz / dist) * force;

                  a.vx = (a.vx ?? 0) - fx;
                  a.vy = (a.vy ?? 0) - fy;
                  a.vz = (a.vz ?? 0) - fz;
                  b.vx = (b.vx ?? 0) + fx;
                  b.vy = (b.vy ?? 0) + fy;
                  b.vz = (b.vz ?? 0) + fz;
                }
              }
            }
          }
        }
      }

      // 4. Sphere shell — gentle push toward target radius
      for (const node of n) {
        const nx = node.x ?? 0;
        const ny = node.y ?? 0;
        const nz = node.z ?? 0;
        let dist = Math.sqrt(nx * nx + ny * ny + nz * nz);
        if (dist === 0) dist = 0.01;

        const dr = (sphereRadius - dist) * 0.01 * alpha;
        node.vx = (node.vx ?? 0) + (nx / dist) * dr;
        node.vy = (node.vy ?? 0) + (ny / dist) * dr;
        node.vz = (node.vz ?? 0) + (nz / dist) * dr;
      }

      // 5. Center gravity — very gentle
      for (const node of n) {
        node.vx = (node.vx ?? 0) - (node.x ?? 0) * 0.001 * alpha;
        node.vy = (node.vy ?? 0) - (node.y ?? 0) * 0.001 * alpha;
        node.vz = (node.vz ?? 0) - (node.z ?? 0) * 0.001 * alpha;
      }

      // 6. Update positions + friction
      const friction = 0.88;
      for (const node of n) {
        node.vx = (node.vx ?? 0) * friction;
        node.vy = (node.vy ?? 0) * friction;
        node.vz = (node.vz ?? 0) * friction;
        node.x = (node.x ?? 0) + node.vx;
        node.y = (node.y ?? 0) + node.vy;
        node.z = (node.z ?? 0) + node.vz;
      }

      alphaRef.current -= alphaDecay * alphaRef.current;

      frameCount++;
      if (frameCount % 4 === 0) {
        requestAnimationFrame(() => setTick(t => t + 1));
      }

      if (alphaRef.current > alphaMin) {
        rafRef.current = requestAnimationFrame(loop);
      } else {
        isRunningRef.current = false;
        requestAnimationFrame(() => setTick(t => t + 1));
      }
    };

    loopFnRef.current = loop;
    rafRef.current = requestAnimationFrame(loop);
    requestAnimationFrame(() => setTick(t => t + 1));

    return () => {
      isRunningRef.current = false;
      loopFnRef.current = null;
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [input, chargeStrength, linkDistance, alphaDecay, alphaMin]);

  const reheat = useCallback((alpha = 0.3) => {
    alphaRef.current = alpha;
    if (!isRunningRef.current && loopFnRef.current) {
      isRunningRef.current = true;
      rafRef.current = requestAnimationFrame(loopFnRef.current);
    }
  }, []);

  const getPositions = useCallback(() => ({
    nodes: nodesRef.current,
    links: linksRef.current,
  }), []);

  return { tick, getPositions, reheat };
}
