import { buildOctree, computeRepulsion } from './octree';

const FRICTION = 0.82;

let positions: Float64Array | null = null;
let velocities: Float64Array | null = null;
let linkSources: Int32Array | null = null;
let linkTargets: Int32Array | null = null;
let linkWeights: Float64Array | null = null;
let clusterCentersX: Float64Array | null = null;
let clusterCentersY: Float64Array | null = null;
let clusterCentersZ: Float64Array | null = null;
let nodeLabels: Int32Array | null = null;
let chargeArray: Float64Array | null = null;
let nodeDegrees: Int32Array | null = null;

let nodeCount = 0;
let linkCount = 0;
let clusterCount = 0;
let boundary = 0;
let alpha = 1;
let alphaDecay = 0.008;
let alphaMin = 0.005;
let chargeStrength = -400;
let linkDistance = 80;
let is2D = true;
let isRunning = false;
let stepCount = 0;

self.onmessage = (e: MessageEvent) => {
  const { type, data } = e.data;

  switch (type) {
    case 'init': {
      nodeCount = data.nodeCount;
      linkCount = data.linkCount;
      clusterCount = data.clusterCount;
      boundary = data.boundary;
      alphaDecay = data.alphaDecay ?? 0.008;
      alphaMin = data.alphaMin ?? 0.005;
      chargeStrength = data.chargeStrength ?? -400;
      linkDistance = data.linkDistance ?? 80;
      is2D = data.dimension === '2d';
      alpha = 0.8;
      stepCount = 0;
      isRunning = true;

      positions = new Float64Array(data.positions);
      velocities = new Float64Array(nodeCount * 3);
      linkSources = new Int32Array(data.linkSources);
      linkTargets = new Int32Array(data.linkTargets);
      linkWeights = new Float64Array(data.linkWeights);
      clusterCentersX = new Float64Array(data.clusterCentersX);
      clusterCentersY = new Float64Array(data.clusterCentersY);
      clusterCentersZ = new Float64Array(data.clusterCentersZ);
      nodeLabels = new Int32Array(data.nodeLabels);

      if (data.chargeArray) {
        chargeArray = new Float64Array(data.chargeArray);
      } else {
        chargeArray = null;
      }

      if (data.nodeDegrees) {
        nodeDegrees = new Int32Array(data.nodeDegrees);
      } else {
        nodeDegrees = null;
      }

      if (is2D) {
        for (let i = 0; i < nodeCount; i++) {
          positions[i * 3 + 2] = 0;
        }
      }

      break;
    }

    case 'step': {
      if (!isRunning || !positions || !velocities) {
        self.postMessage({ type: 'step', alpha, isRunning: false, positions: null });
        return;
      }

      step();

      const posCopy = new Float64Array(positions);
      const converged = !isRunning;
      const telemetry = converged ? computeTelemetry() : null;
      self.postMessage(
        { type: 'step', alpha, isRunning, positions: posCopy.buffer, telemetry }
      );

      break;
    }

    case 'reheat': {
      alpha = data?.alpha ?? 0.3;
      isRunning = true;
      break;
    }

    case 'pause': {
      isRunning = false;
      break;
    }

    case 'resume': {
      if (alpha > alphaMin) isRunning = true;
      break;
    }

    case 'stop': {
      isRunning = false;
      break;
    }
  }
};

function step(): void {
  if (!positions || !velocities) return;

  stepCount++;

  applyClusterAttraction();
  applyLinkForce();

  const octree = buildOctree(positions, nodeCount);
  if (chargeArray) {
    computeRepulsionWithCharge(octree, positions, velocities, nodeCount, chargeArray, alpha);
  } else {
    computeRepulsion(octree, positions, velocities, nodeCount, chargeStrength, alpha);
  }

  applyBoundary();
  applyCenterGravity();
  integratePositions();

  if (is2D) {
    flattenZ();
  }

  const effectiveDecay = stepCount < 300 ? alphaDecay * 0.6 : alphaDecay;
  alpha -= effectiveDecay * alpha;
  if (alpha <= alphaMin) {
    isRunning = false;
  }
}

function applyClusterAttraction(): void {
  if (!positions || !velocities || !nodeLabels || !clusterCentersX || !clusterCentersY || !clusterCentersZ) return;

  for (let i = 0; i < nodeCount; i++) {
    const ci = nodeLabels[i];
    if (ci < 0 || ci >= clusterCount) continue;
    const idx = i * 3;
    const dx = clusterCentersX[ci] - positions[idx];
    const dy = clusterCentersY[ci] - positions[idx + 1];
    const dz = is2D ? 0 : clusterCentersZ[ci] - positions[idx + 2];
    const deg = nodeDegrees ? nodeDegrees[i] : 1;
    const strength = 0.008 * alpha * (1 + Math.sqrt(deg) * 0.05);
    velocities[idx] += dx * strength;
    velocities[idx + 1] += dy * strength;
    velocities[idx + 2] += dz * strength;
  }
}

function applyLinkForce(): void {
  if (!positions || !velocities || !linkSources || !linkTargets || !linkWeights) return;

  for (let i = 0; i < linkCount; i++) {
    const si = linkSources[i] * 3;
    const ti = linkTargets[i] * 3;
    const dx = positions[ti] - positions[si];
    const dy = positions[ti + 1] - positions[si + 1];
    const dz = is2D ? 0 : positions[ti + 2] - positions[si + 2];
    let dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (dist === 0) dist = 0.01;

    const strength = linkWeights[i] * alpha * 0.6;
    const force = (dist - linkDistance) * strength;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    const fz = (dz / dist) * force;

    velocities[si] += fx;
    velocities[si + 1] += fy;
    velocities[si + 2] += fz;
    velocities[ti] -= fx;
    velocities[ti + 1] -= fy;
    velocities[ti + 2] -= fz;
  }
}

function applyBoundary(): void {
  if (!positions || !velocities) return;

  const boundary2 = boundary * boundary;

  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    const x = positions[idx], y = positions[idx + 1], z = positions[idx + 2];
    const r2 = x * x + y * y + (is2D ? 0 : z * z);
    if (r2 > boundary2) {
      const r = Math.sqrt(r2);
      const excess = (r - boundary) / boundary;
      const k = 0.05 * alpha * excess;
      velocities[idx] -= (x / r) * r * k;
      velocities[idx + 1] -= (y / r) * r * k;
      if (!is2D) {
        velocities[idx + 2] -= (z / r) * r * k;
      }
    }
  }
}

function applyCenterGravity(): void {
  if (!positions || !velocities) return;

  const strength = 0.005 * alpha;
  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    velocities[idx] -= positions[idx] * strength;
    velocities[idx + 1] -= positions[idx + 1] * strength;
    if (!is2D) {
      velocities[idx + 2] -= positions[idx + 2] * strength;
    }
  }
}

function integratePositions(): void {
  if (!positions || !velocities) return;

  const MAX_POS = 5000;
  const MAX_VEL = 200;

  for (let i = 0; i < nodeCount * 3; i++) {
    velocities[i] *= FRICTION;

    if (!isFinite(velocities[i])) velocities[i] = 0;
    if (velocities[i] > MAX_VEL) velocities[i] = MAX_VEL;
    if (velocities[i] < -MAX_VEL) velocities[i] = -MAX_VEL;

    positions[i] += velocities[i];

    if (!isFinite(positions[i])) positions[i] = (Math.random() - 0.5) * 10;
    if (positions[i] > MAX_POS) { positions[i] = MAX_POS; velocities[i] = 0; }
    if (positions[i] < -MAX_POS) { positions[i] = -MAX_POS; velocities[i] = 0; }
  }
}

function flattenZ(): void {
  if (!positions || !velocities) return;

  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    positions[idx + 2] = 0;
    velocities[idx + 2] = 0;
  }
}

function computeRepulsionWithCharge(
  root: import('./octree').OctreeNode,
  positions: Float64Array,
  velocities: Float64Array,
  count: number,
  chargeArray: Float64Array,
  alpha: number
): void {
  const softening = 25;
  for (let i = 0; i < count; i++) {
    const idx = i * 3;
    const px = positions[idx];
    const py = positions[idx + 1];
    const pz = is2D ? 0 : positions[idx + 2];
    let fx = 0, fy = 0, fz = 0;

    traverseWithCharge(root, px, py, pz, alpha, softening, (dx, dy, dz, force) => {
      fx += dx * force;
      fy += dy * force;
      fz += dz * force;
    });

    velocities[idx] += fx;
    velocities[idx + 1] += fy;
    if (!is2D) {
      velocities[idx + 2] += fz;
    }

    if (!isFinite(velocities[idx])) velocities[idx] = 0;
    if (!isFinite(velocities[idx + 1])) velocities[idx + 1] = 0;
    if (!isFinite(velocities[idx + 2])) velocities[idx + 2] = 0;
  }
}

function traverseWithCharge(
  node: import('./octree').OctreeNode,
  px: number, py: number, pz: number,
  alpha: number,
  softening: number,
  onForce: (dx: number, dy: number, dz: number, force: number) => void
): void {
  if (node.mass === 0) return;

  const dx = node.x - px;
  const dy = node.y - py;
  const dz = node.z - pz;
  const distSq = dx * dx + dy * dy + dz * dz;

  if (node.isLeaf) {
    if (distSq < 0.1) return;
    const dist = Math.sqrt(distSq);
    // Force is proportional to the other node's charge (node.mass)
    const force = (node.mass * alpha) / (distSq + softening);
    onForce(dx / dist, dy / dist, dz / dist, force);
    return;
  }

  const THETA = 0.5;
  const s = node.size;
  if ((s * s) / distSq < THETA * THETA) {
    const dist = Math.sqrt(Math.max(distSq, 0.01));
    // Force is proportional to the accumulated charge of the octree cell (node.mass)
    const force = (node.mass * alpha) / (distSq + softening);
    onForce(dx / dist, dy / dist, dz / dist, force);
    return;
  }

  for (const child of node.children) {
    if (child) traverseWithCharge(child, px, py, pz, alpha, softening, onForce);
  }
}

function computeTelemetry(): { centroidOffset: number; densityVariance: number; isolatedNodeCount: number; longestEdgeRatio: number; occupiedAreaRatio: number } {
  if (!positions || !nodeDegrees || nodeCount === 0) {
    return { centroidOffset: 0, densityVariance: 0, isolatedNodeCount: 0, longestEdgeRatio: 0, occupiedAreaRatio: 0 };
  }

  let cx = 0, cy = 0;
  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    cx += positions[idx];
    cy += positions[idx + 1];
  }
  cx /= nodeCount;
  cy /= nodeCount;

  const centroidOffset = Math.sqrt(cx * cx + cy * cy);

  const GRID = 10;
  const minMax = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    const x = positions[idx], y = positions[idx + 1];
    if (x < minMax.minX) minMax.minX = x;
    if (x > minMax.maxX) minMax.maxX = x;
    if (y < minMax.minY) minMax.minY = y;
    if (y > minMax.maxY) minMax.maxY = y;
  }
  const rangeX = minMax.maxX - minMax.minX || 1;
  const rangeY = minMax.maxY - minMax.minY || 1;

  const buckets = new Int32Array(GRID * GRID);
  for (let i = 0; i < nodeCount; i++) {
    const idx = i * 3;
    const bx = Math.min(GRID - 1, Math.max(0, Math.floor((positions[idx] - minMax.minX) / rangeX * GRID)));
    const by = Math.min(GRID - 1, Math.max(0, Math.floor((positions[idx + 1] - minMax.minY) / rangeY * GRID)));
    buckets[by * GRID + bx]++;
  }

  const mean = nodeCount / (GRID * GRID);
  let varSum = 0;
  let occupied = 0;
  for (let i = 0; i < GRID * GRID; i++) {
    varSum += (buckets[i] - mean) ** 2;
    if (buckets[i] > 0) occupied++;
  }
  const densityVariance = varSum / (GRID * GRID);

  let isolatedCount = 0;
  for (let i = 0; i < nodeCount; i++) {
    if (nodeDegrees[i] === 0) isolatedCount++;
  }

  let maxEdgeLen = 0;
  let edgeLenSum = 0;
  if (linkSources && linkTargets) {
    for (let i = 0; i < linkCount; i++) {
      const si = linkSources[i] * 3;
      const ti = linkTargets[i] * 3;
      const dx = positions[ti] - positions[si];
      const dy = positions[ti + 1] - positions[si + 1];
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len > maxEdgeLen) maxEdgeLen = len;
      edgeLenSum += len;
    }
  }
  const medianEdge = linkCount > 0 ? edgeLenSum / linkCount : 1;
  const longestEdgeRatio = medianEdge > 0 ? maxEdgeLen / medianEdge : 0;

  const occupiedAreaRatio = occupied / (GRID * GRID);

  return { centroidOffset, densityVariance, isolatedNodeCount: isolatedCount, longestEdgeRatio, occupiedAreaRatio };
}

export {};
