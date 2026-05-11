const CELL_SIZE = 120;
const NEIGHBOR_OFFSETS = [-1, 0, 1];

function hashKey(x: number, y: number, z: number): string {
  return `${Math.floor(x / CELL_SIZE)},${Math.floor(y / CELL_SIZE)},${Math.floor(z / CELL_SIZE)}`;
}

export function buildGrid(nodes: { x?: number; y?: number; z?: number }[]): Map<string, number[]> {
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

export function applyRepulsion(
  nodes: { x?: number; y?: number; z?: number; vx?: number; vy?: number; vz?: number }[],
  grid: Map<string, number[]>,
  chargeStrength: number,
  alpha: number
): void {
  // Adaptive repulsion distance based on scale
  const repulsionRange = CELL_SIZE * 1.5;
  const repulsionRangeSq = repulsionRange * repulsionRange;

  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
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
            const b = nodes[j];
            let dx = (b.x ?? 0) - ax;
            let dy = (b.y ?? 0) - ay;
            let dz = (b.z ?? 0) - az;
            let distSq = dx * dx + dy * dy + dz * dz;
            
            // Add jitter if nodes are exactly on top of each other
            if (distSq < 0.1) {
              dx = (Math.random() - 0.5) * 2;
              dy = (Math.random() - 0.5) * 2;
              dz = (Math.random() - 0.5) * 2;
              distSq = dx * dx + dy * dy + dz * dz;
            }
            
            if (distSq < repulsionRangeSq) {
              const dist = Math.sqrt(distSq);
              // Use a softening parameter (+ 25) to prevent explosive forces when nodes are too close
              const force = (chargeStrength * alpha) / (distSq + 25);
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              const fz = (dz / dist) * force;

              a.vx = (a.vx ?? 0) + fx;
              a.vy = (a.vy ?? 0) + fy;
              a.vz = (a.vz ?? 0) + fz;
              b.vx = (b.vx ?? 0) - fx;
              b.vy = (b.vy ?? 0) - fy;
              b.vz = (b.vz ?? 0) - fz;
            }
          }
        }
      }
    }
  }
}
