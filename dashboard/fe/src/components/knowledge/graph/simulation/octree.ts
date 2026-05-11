export interface OctreeNode {
  x: number;
  y: number;
  z: number;
  mass: number;
  children: (OctreeNode | null)[];
  isLeaf: boolean;
  size: number;
}

const MAX_DEPTH = 12;
const THETA = 0.5;

function createNode(cx: number, cy: number, cz: number, size: number): OctreeNode {
  return { x: 0, y: 0, z: 0, mass: 0, children: new Array(8).fill(null), isLeaf: true, size };
}

function octant(cx: number, cy: number, cz: number, px: number, py: number, pz: number): number {
  let idx = 0;
  if (px >= cx) idx |= 1;
  if (py >= cy) idx |= 2;
  if (pz >= cz) idx |= 4;
  return idx;
}

function childCenter(cx: number, cy: number, cz: number, size: number, oct: number): { x: number; y: number; z: number; size: number } {
  const hs = size * 0.5;
  return {
    x: cx + (oct & 1 ? hs : -hs),
    y: cy + (oct & 2 ? hs : -hs),
    z: cz + (oct & 4 ? hs : -hs),
    size: hs,
  };
}

export function buildOctree(
  positions: Float64Array,
  count: number,
  chargeArray?: Float64Array
): OctreeNode {
  let min_x = Infinity, min_y = Infinity, min_z = Infinity;
  let max_x = -Infinity, max_y = -Infinity, max_z = -Infinity;

  for (let i = 0; i < count; i++) {
    const idx = i * 3;
    const px = positions[idx];
    const py = positions[idx + 1];
    const pz = positions[idx + 2];
    if (px < min_x) min_x = px;
    if (py < min_y) min_y = py;
    if (pz < min_z) min_z = pz;
    if (px > max_x) max_x = px;
    if (py > max_y) max_y = py;
    if (pz > max_z) max_z = pz;
  }

  const cx = (min_x + max_x) * 0.5;
  const cy = (min_y + max_y) * 0.5;
  const cz = (min_z + max_z) * 0.5;
  const size = Math.max(max_x - min_x, max_y - min_y, max_z - min_z, 1) * 1.01;

  const root = createNode(cx, cy, cz, size);

  for (let i = 0; i < count; i++) {
    const idx = i * 3;
    const charge = chargeArray ? chargeArray[i] : 1;
    insertNode(root, positions[idx], positions[idx + 1], positions[idx + 2], charge, cx, cy, cz, size, 0);
  }

  return root;
}

function insertNode(
  node: OctreeNode,
  px: number, py: number, pz: number, charge: number,
  cx: number, cy: number, cz: number,
  size: number,
  depth: number
): void {
  if (depth >= MAX_DEPTH) {
    node.x = (node.x * node.mass + px * charge) / (node.mass + charge);
    node.y = (node.y * node.mass + py * charge) / (node.mass + charge);
    node.z = (node.z * node.mass + pz * charge) / (node.mass + charge);
    node.mass += charge;
    return;
  }

  if (node.mass === 0) {
    node.x = px;
    node.y = py;
    node.z = pz;
    node.mass = charge;
    return;
  }

  if (node.isLeaf) {
    const oldX = node.x;
    const oldY = node.y;
    const oldZ = node.z;
    const oldCharge = node.mass;
    node.isLeaf = false;

    const oldOct = octant(cx, cy, cz, oldX, oldY, oldZ);
    const cc = childCenter(cx, cy, cz, size, oldOct);
    const child = createNode(cc.x, cc.y, cc.z, cc.size);
    insertNode(child, oldX, oldY, oldZ, oldCharge, cc.x, cc.y, cc.z, cc.size, depth + 1);
    node.children[oldOct] = child;

    node.x = 0; node.y = 0; node.z = 0; node.mass = 0;
  }

  node.x = (node.x * node.mass + px * charge) / (node.mass + charge);
  node.y = (node.y * node.mass + py * charge) / (node.mass + charge);
  node.z = (node.z * node.mass + pz * charge) / (node.mass + charge);
  node.mass += charge;

  const oct = octant(cx, cy, cz, px, py, pz);
  let child = node.children[oct];
  if (!child) {
    const cc = childCenter(cx, cy, cz, size, oct);
    child = createNode(cc.x, cc.y, cc.z, cc.size);
    node.children[oct] = child;
  }
  const cc = childCenter(cx, cy, cz, size, oct);
  insertNode(child, px, py, pz, charge, cc.x, cc.y, cc.z, cc.size, depth + 1);
}

export function computeRepulsion(
  root: OctreeNode,
  positions: Float64Array,
  velocities: Float64Array,
  count: number,
  chargeStrength: number,
  alpha: number
): void {
  const softening = 25;
  for (let i = 0; i < count; i++) {
    const idx = i * 3;
    const px = positions[idx];
    const py = positions[idx + 1];
    const pz = positions[idx + 2];
    let fx = 0, fy = 0, fz = 0;

    traverse(root, px, py, pz, chargeStrength, alpha, softening, (dx, dy, dz, force) => {
      fx += dx * force;
      fy += dy * force;
      fz += dz * force;
    });

    velocities[idx] += fx;
    velocities[idx + 1] += fy;
    velocities[idx + 2] += fz;
  }
}

function traverse(
  node: OctreeNode,
  px: number, py: number, pz: number,
  chargeStrength: number,
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
    const force = (chargeStrength * alpha) / (distSq + softening);
    onForce(dx / dist, dy / dist, dz / dist, force);
    return;
  }

  const s = node.size;
  if ((s * s) / distSq < THETA * THETA) {
    const dist = Math.sqrt(Math.max(distSq, 0.01));
    const force = (chargeStrength * alpha * node.mass) / (distSq + softening);
    onForce(dx / dist, dy / dist, dz / dist, force);
    return;
  }

  for (const child of node.children) {
    if (child) traverse(child, px, py, pz, chargeStrength, alpha, softening, onForce);
  }
}
