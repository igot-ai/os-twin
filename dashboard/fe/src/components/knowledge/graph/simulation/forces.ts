import type { SimNode, SimLink } from './types';
import { buildGrid, applyRepulsion } from './spatial-hash';

export function applyClusterAttraction(
  nodes: SimNode[],
  clusterCenters: Map<string, { x: number; y: number; z: number }>,
  alpha: number
): void {
  for (const node of nodes) {
    const center = clusterCenters.get(node.label);
    if (!center) continue;
    const dx = center.x - (node.x ?? 0);
    const dy = center.y - (node.y ?? 0);
    const dz = center.z - (node.z ?? 0);
    const deg = node.degree ?? 1;
    const strength = 0.012 * alpha * (1 + Math.sqrt(deg) * 0.1);
    node.vx = (node.vx ?? 0) + dx * strength;
    node.vy = (node.vy ?? 0) + dy * strength;
    node.vz = (node.vz ?? 0) + dz * strength;
  }
}

const LINK_BASE = 100;
const LINK_SPREAD = 45;

export function applyLinkForce(
  links: SimLink[],
  _linkDistance: number,
  alpha: number
): void {
  for (const link of links) {
    const source = link.source as SimNode;
    const target = link.target as SimNode;
    const dx = (target.x ?? 0) - (source.x ?? 0);
    const dy = (target.y ?? 0) - (source.y ?? 0);
    const dz = (target.z ?? 0) - (source.z ?? 0);
    let dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (dist === 0) dist = 0.01;

    const srcDeg = source.degree ?? 1;
    const tgtDeg = target.degree ?? 1;
    const hubDeg = Math.max(srcDeg, tgtDeg);
    const excess = Math.max(hubDeg - 2, 0);
    const targetDist = LINK_BASE + LINK_SPREAD * Math.sqrt(excess);

    const strength = (1 / Math.sqrt(1 + Math.min(srcDeg, tgtDeg))) * alpha * 0.6;
    const force = (dist - targetDist) * strength;
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
}

export function applyRepulsionForce(
  nodes: SimNode[],
  chargeStrength: number,
  alpha: number
): void {
  const grid = buildGrid(nodes);
  applyRepulsion(nodes, grid, chargeStrength, alpha);
}

export function applyBoundary(
  nodes: SimNode[],
  boundary: number,
  alpha: number,
  is2D: boolean
): void {
  const boundary2 = boundary * boundary;
  for (const node of nodes) {
    const nx = node.x ?? 0;
    const ny = node.y ?? 0;
    const nz = node.z ?? 0;
    const r2 = nx * nx + ny * ny + (is2D ? 0 : nz * nz);
    if (r2 > boundary2) {
      const r = Math.sqrt(r2);
      const excess = (r - boundary) / boundary;
      const k = 0.05 * alpha * excess;
      node.vx = (node.vx ?? 0) - (nx / r) * r * k;
      node.vy = (node.vy ?? 0) - (ny / r) * r * k;
      if (!is2D) {
        node.vz = (node.vz ?? 0) - (nz / r) * r * k;
      }
    }
  }
}

export function applyCenterGravity(
  nodes: SimNode[],
  alpha: number,
  is2D: boolean
): void {
  const strength = 0.005 * alpha;
  for (const node of nodes) {
    node.vx = (node.vx ?? 0) - (node.x ?? 0) * strength;
    node.vy = (node.vy ?? 0) - (node.y ?? 0) * strength;
    if (!is2D) {
      node.vz = (node.vz ?? 0) - (node.z ?? 0) * strength;
    }
  }
}

export function integratePositions(
  nodes: SimNode[],
  friction: number = 0.88,
  is2D: boolean = true
): void {
  for (const node of nodes) {
    node.vx = (node.vx ?? 0) * friction;
    node.vy = (node.vy ?? 0) * friction;
    node.vz = is2D ? 0 : (node.vz ?? 0) * friction;
    node.x = (node.x ?? 0) + node.vx;
    node.y = (node.y ?? 0) + node.vy;
    node.z = is2D ? 0 : (node.z ?? 0) + node.vz;
  }
}
