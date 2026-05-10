/**
 * NodeLabels — HTML overlay labels for graph nodes.
 *
 * Uses @react-three/drei's Html component to render labels
 * at each node's position. Labels are only shown when zoomed in
 * enough (controlled by the showLabels prop).
 *
 * Performance: Only renders labels for nodes that are visible
 * and limits to maxLabels at a time.
 */

import React, { useMemo } from 'react';
import { Html } from '@react-three/drei';
import type { SimNode } from './useForceSimulation';
import { getNodeColor } from '../constants';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface NodeLabelsProps {
  nodes: SimNode[];
  ignitionSet: Set<string>;
  selectedId: string | null;
  /** Whether to show labels at all (based on zoom level) */
  showLabels: boolean;
  /** Max number of labels to render */
  maxLabels?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NodeLabels({
  nodes,
  ignitionSet,
  selectedId,
  showLabels,
  maxLabels = 200,
}: NodeLabelsProps) {
  // Prioritize: selected > ignition > high score
  const visibleNodes = useMemo(() => {
    if (!showLabels) return [];

    const sorted = [...nodes].sort((a, b) => {
      if (a.id === selectedId) return -1;
      if (b.id === selectedId) return 1;
      if (ignitionSet.has(a.id) && !ignitionSet.has(b.id)) return -1;
      if (!ignitionSet.has(a.id) && ignitionSet.has(b.id)) return 1;
      return b.score - a.score;
    });

    return sorted.slice(0, maxLabels);
  }, [nodes, ignitionSet, selectedId, showLabels, maxLabels]);

  if (!showLabels || visibleNodes.length === 0) return null;

  return (
    <group>
      {visibleNodes.map(node => {
        const x = node.x ?? 0;
        const y = -(node.y ?? 0); // Flip Y
        const z = node.z ?? 0;
        const isIgnition = ignitionSet.has(node.id);
        const isSelected = node.id === selectedId;
        const label = node.name.length > 20 ? node.name.slice(0, 18) + '…' : node.name;

        return (
          <Html
            key={node.id}
            position={[x, y, z]}
            center
            distanceFactor={10}
            style={{
              pointerEvents: 'none',
              userSelect: 'none',
              whiteSpace: 'nowrap',
            }}
            zIndexRange={[0, 0]}
          >
            <span
              style={{
                fontSize: isSelected ? 11 : 9,
                fontWeight: isSelected ? 600 : 400,
                color: isIgnition ? getNodeColor(node.label) : 'rgba(30, 41, 59, 0.85)',
                opacity: isSelected ? 1 : Math.max(node.brightness ?? 0.3, 0.5),
                fontFamily: 'Inter, system-ui, sans-serif',
                textShadow: '0 1px 2px rgba(255,255,255,0.9)',
                transform: `translateY(${(5 + Math.min(node.degree, 20) * 0.4 + node.score * 2 + (isSelected ? 3 : 0)) * 0.7}px)`,
              }}
            >
              {label}
            </span>
          </Html>
        );
      })}
    </group>
  );
}
