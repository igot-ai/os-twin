export function fibonacciSphere(count: number, radius: number): { x: number; y: number; z: number }[] {
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

export function computeClusterCenters(
  nodes: { label: string }[],
  sphereRadius: number
): Map<string, { x: number; y: number; z: number }> {
  const uniqueLabels = [...new Set(nodes.map(n => n.label))].sort();
  const fibPoints = fibonacciSphere(uniqueLabels.length, sphereRadius);
  const centers = new Map<string, { x: number; y: number; z: number }>();
  uniqueLabels.forEach((label, i) => {
    centers.set(label, fibPoints[i]);
  });
  return centers;
}

export interface CommunityInfo {
  id: number;
  size: number;
}

export function computeCommunityCenters(
  communityIds: (number | undefined)[],
  boundary: number,
  is2D: boolean
): { centersX: Float64Array; centersY: Float64Array; centersZ: Float64Array; communityIndex: Int32Array; uniqueCommunities: number[] } {
  const communitySizes = new Map<number, number>();
  for (const cid of communityIds) {
    const id = cid ?? -1;
    communitySizes.set(id, (communitySizes.get(id) ?? 0) + 1);
  }

  const uniqueCommunities = [...communitySizes.keys()].sort((a, b) => a - b);
  const communityIndexMap = new Map(uniqueCommunities.map((id, i) => [id, i]));

  const totalSize = [...communitySizes.values()].reduce((a, b) => a + b, 0) || 1;

  const centersX = new Float64Array(uniqueCommunities.length);
  const centersY = new Float64Array(uniqueCommunities.length);
  const centersZ = new Float64Array(uniqueCommunities.length);

  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  let cumulativeArea = 0;

  for (let i = 0; i < uniqueCommunities.length; i++) {
    const cid = uniqueCommunities[i];
    const size = communitySizes.get(cid) ?? 1;
    const fraction = size / totalSize;

    // t is the center of the area slice for this community, from 0 to 1
    const t = cumulativeArea + fraction * 0.5;
    cumulativeArea += fraction;

    const y = 1 - t * 2; // Correctly maps [0, 1] to [1, -1]
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = goldenAngle * i;

    // Bigger communities sit closer to the center to avoid fighting for surface area
    const communityRadius = boundary * (0.3 + 0.6 * (1 - Math.sqrt(fraction)));

    centersX[i] = Math.cos(theta) * r * communityRadius;
    centersY[i] = y * communityRadius;
    centersZ[i] = is2D ? 0 : Math.sin(theta) * r * communityRadius;
  }

  const communityIndex = new Int32Array(communityIds.length);
  for (let i = 0; i < communityIds.length; i++) {
    communityIndex[i] = communityIndexMap.get(communityIds[i] ?? -1) ?? -1;
  }

  return { centersX, centersY, centersZ, communityIndex, uniqueCommunities };
}

export function computeConnectedComponents(
  nodeIds: string[],
  links: { source: string; target: string }[]
): number[] {
  const nodeIndex = new Map(nodeIds.map((id, i) => [id, i]));
  const adjacency = new Map<number, number[]>();
  for (let i = 0; i < nodeIds.length; i++) {
    adjacency.set(i, []);
  }

  for (const link of links) {
    const si = nodeIndex.get(link.source);
    const ti = nodeIndex.get(link.target);
    if (si !== undefined && ti !== undefined) {
      adjacency.get(si)!.push(ti);
      adjacency.get(ti)!.push(si);
    }
  }

  const componentIds = new Int32Array(nodeIds.length).fill(-1);
  let currentComponent = 0;

  for (let i = 0; i < nodeIds.length; i++) {
    if (componentIds[i] >= 0) continue;
    const queue = [i];
    componentIds[i] = currentComponent;
    while (queue.length > 0) {
      const node = queue.shift()!;
      for (const neighbor of adjacency.get(node) ?? []) {
        if (componentIds[neighbor] < 0) {
          componentIds[neighbor] = currentComponent;
          queue.push(neighbor);
        }
      }
    }
    currentComponent++;
  }

  return Array.from(componentIds);
}
