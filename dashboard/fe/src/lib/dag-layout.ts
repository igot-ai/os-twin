import { EpicDocument } from './epic-parser';
import { DAG, DAGNodeRaw } from '@/types';

/**
 * Derive a DAG structure from a parsed EpicDocument.
 * This replaces the backend /dag endpoint for authoring mode.
 * Reuses the existing DAG type so DAGViewer can render it.
 */
export function deriveDAGFromDocument(doc: EpicDocument): DAG {
  const nodes: Record<string, DAGNodeRaw> = {};
  const adj: Record<string, string[]> = {};
  const inDegree: Record<string, number> = {};
  const epicMap = new Map(doc.epics.map(e => [e.ref, e]));

  // 1. Build nodes from doc.epics
  for (const epic of doc.epics) {
    const ref = epic.ref;
    const role = epic.frontmatter.get('Owner') || epic.frontmatter.get('owner') || 'engineer';
    
    nodes[ref] = {
      room_id: `room-${ref.toLowerCase()}`, // Mock room_id
      role: role,
      candidate_roles: [],
      depends_on: epic.depends_on,
      dependents: [],
      depth: 0,
      on_critical_path: false,
    };
    adj[ref] = [];
    inDegree[ref] = 0;
  }

  // 2. Build adjacency list from depends_on and compute in-degrees
  for (const epic of doc.epics) {
    const toRef = epic.ref;
    for (const fromRef of epic.depends_on) {
      if (nodes[fromRef]) {
        adj[fromRef].push(toRef);
        nodes[fromRef].dependents.push(toRef);
        inDegree[toRef]++;
      }
    }
  }

  // 3. Topological sort (Kahn's algorithm)
  const queue: string[] = [];
  const initialInDegree = { ...inDegree };
  for (const ref of Object.keys(nodes)) {
    if (initialInDegree[ref] === 0) {
      queue.push(ref);
    }
  }

  const topologicalOrder: string[] = [];
  const waves: Record<string, string[]> = {};
  const nodeDepths: Record<string, number> = {};

  // Initialize depths
  for (const ref of Object.keys(nodes)) {
    nodeDepths[ref] = 0;
  }

  let head = 0;
  while (head < queue.length) {
    const u = queue[head++];
    topologicalOrder.push(u);

    const depth = nodeDepths[u];
    if (!waves[depth]) waves[depth] = [];
    waves[depth].push(u);
    nodes[u].depth = depth;

    for (const v of adj[u]) {
      initialInDegree[v]--;
      nodeDepths[v] = Math.max(nodeDepths[v], depth + 1);
      if (initialInDegree[v] === 0) {
        queue.push(v);
      }
    }
  }

  const maxDepth = Object.keys(waves).length > 0 ? Math.max(...Object.keys(waves).map(Number)) : 0;

  // 5. Compute critical path (longest path in DAG)
  const dist: Record<string, number> = {};
  const parent: Record<string, string | null> = {};

  for (const ref of topologicalOrder) {
    dist[ref] = 1;
    parent[ref] = null;
    const epic = epicMap.get(ref);
    if (epic) {
      for (const dep of epic.depends_on) {
        if (nodes[dep] && dist[dep] + 1 > dist[ref]) {
          dist[ref] = dist[dep] + 1;
          parent[ref] = dep;
        }
      }
    }
  }

  const criticalPath: string[] = [];
  let maxDist = 0;
  let lastNode: string | null = null;

  for (const ref of topologicalOrder) {
    if (dist[ref] > maxDist) {
      maxDist = dist[ref];
      lastNode = ref;
    }
  }

  if (lastNode) {
    let curr: string | null = lastNode;
    while (curr) {
      criticalPath.unshift(curr);
      nodes[curr].on_critical_path = true;
      curr = parent[curr];
    }
  }

  return {
    generated_at: new Date().toISOString(),
    total_nodes: doc.epics.length,
    max_depth: maxDepth,
    nodes,
    topological_order: topologicalOrder,
    critical_path: criticalPath,
    critical_path_length: criticalPath.length,
    waves,
  };
}

/**
 * Detect if adding an edge would create a cycle.
 * Used to validate drag-to-connect before committing.
 * fromRef -> toRef edge (toRef depends on fromRef)
 */
export function wouldCreateCycle(
  doc: EpicDocument, fromRef: string, toRef: string
): boolean {
  if (fromRef === toRef) return true;

  const epicMap = new Map(doc.epics.map(e => [e.ref, e]));
  
  // Edge: fromRef -> toRef (means toRef depends_on fromRef)
  // Cycle exists if fromRef already depends on toRef (directly or indirectly)
  // Path search: fromRef -> ... -> toRef
  
  const q = [fromRef];
  const seen = new Set<string>();
  seen.add(fromRef);
  
  while (q.length > 0) {
    const curr = q.shift()!;
    const epic = epicMap.get(curr);
    if (epic) {
      for (const dep of epic.depends_on) {
        if (dep === toRef) return true;
        if (!seen.has(dep)) {
          seen.add(dep);
          q.push(dep);
        }
      }
    }
  }

  return false;
}
