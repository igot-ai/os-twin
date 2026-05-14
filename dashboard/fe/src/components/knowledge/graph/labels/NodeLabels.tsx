import React, { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';
import type { SimNode } from '../simulation/types';
import { getNodeColor } from '../../constants';

interface NodeLabelsProps {
  nodes: SimNode[];
  ignitionSet: Set<string>;
  selectedId: string | null;
  maxLabels?: number;
  nodeBrightness: Map<string, number>;
  highlightedLabels?: Set<string>;
  neighborhoodIds?: Set<string>;
}

const MAX_LABELS = 5000;

interface LabelEntry {
  id: string;
  name: string;
  position: THREE.Vector3;
  color: string;
  opacity: number;
  fontSize: number;
}

export default function NodeLabels({
  nodes,
  ignitionSet,
  selectedId,
  maxLabels = 1000,
  nodeBrightness,
  highlightedLabels,
  neighborhoodIds,
}: NodeLabelsProps) {
  const groupRef = useRef<THREE.Group>(null);
  const labelRefs = useRef<Map<string, THREE.Mesh>>(new Map());

  const visibleNodes = useMemo(() => {
    const hasHighlight = highlightedLabels && highlightedLabels.size > 0;
    const hasNeighborhood = neighborhoodIds && neighborhoodIds.size > 0;

    const sorted = [...nodes].sort((a, b) => {
      if (a.id === selectedId) return -1;
      if (b.id === selectedId) return 1;
      const aIgnited = ignitionSet.has(a.id);
      const bIgnited = ignitionSet.has(b.id);
      if (aIgnited && !bIgnited) return -1;
      if (!aIgnited && bIgnited) return 1;
      return b.score - a.score;
    });

    return sorted
      .filter(n => {
        if (hasHighlight && !highlightedLabels.has(n.label)) return false;
        if (hasNeighborhood && !neighborhoodIds.has(n.id)) return false;
        return true;
      })
      .slice(0, Math.min(maxLabels, MAX_LABELS));
  }, [nodes, ignitionSet, selectedId, maxLabels, highlightedLabels, neighborhoodIds]);

  const labelEntries = useMemo(() => {
    const entries: LabelEntry[] = [];
    for (const node of visibleNodes) {
      const x = node.x ?? 0;
      const y = -(node.y ?? 0);
      const z = node.z ?? 0;
      const isIgnition = ignitionSet.has(node.id);
      const isSelected = node.id === selectedId;
      const label = node.name.length > 24 ? node.name.slice(0, 22) + '\u2026' : node.name;
      const nodeColor = getNodeColor(node.label);
      const color = isIgnition ? nodeColor : nodeColor;
      const opacity = isSelected ? 1.0 : Math.max(nodeBrightness.get(node.id) ?? 0.3, 0.5);
      const degree = node.degree ?? 0;
      // Match the 25x proportional scale for the labels to float correctly above the nodes
      const rawSize = degree > 0 ? degree * 10 : 5;
      const baseScale = rawSize * 25;
      // Adjust yOffset multiplier so it clears the shape radius properly
      const yOffset = (baseScale * 0.5 + (isSelected ? 50 : 0)) + baseScale * 0.2;
      // Scale font size proportionally to the node scale so it's readable
      const baseFontSize = baseScale * 0.4;
      const fontSize = isSelected ? baseFontSize * 1.3 : baseFontSize;

      entries.push({
        id: node.id,
        name: label,
        position: new THREE.Vector3(x, y - yOffset, z),
        color,
        opacity,
        fontSize,
      });
    }

    return entries;
  }, [visibleNodes, ignitionSet, selectedId, nodeBrightness]);

  useFrame(({ camera }) => {
    for (const entry of labelEntries) {
      const ref = labelRefs.current.get(entry.id);
      if (!ref) continue;

      const node = nodes.find(n => n.id === entry.id);
      if (!node) continue;

      const x = node.x ?? 0;
      const y = -(node.y ?? 0);
      const z = node.z ?? 0;
      const isSelected = node.id === selectedId;
      const degree = node.degree ?? 0;
      const rawSize = degree > 0 ? degree * 10 : 5;
      const baseScale = rawSize * 25;
      const yOffset = (baseScale * 0.5 + (isSelected ? 50 : 0)) + baseScale * 0.2;

      ref.position.set(x, y - yOffset, z);
      ref.quaternion.copy(camera.quaternion);
    }
  });

  useEffect(() => {
    const currentIds = new Set(labelEntries.map(e => e.id));
    for (const [id] of labelRefs.current) {
      if (!currentIds.has(id)) {
        labelRefs.current.delete(id);
      }
    }
  }, [labelEntries]);

  return (
    <group ref={groupRef}>
      {labelEntries.map((entry) => (
        <Text
          key={entry.id}
          ref={(el) => {
            if (el) labelRefs.current.set(entry.id, el);
          }}
          position={entry.position}
          fontSize={entry.fontSize}
          color={entry.color}
          fillOpacity={entry.opacity}
          anchorX="center"
          anchorY="top"
          depthOffset={-1}
          outlineWidth="5%"
          outlineColor="#000000"
          outlineOpacity={0.7}
          renderOrder={10}
        >
          {entry.name}
        </Text>
      ))}
    </group>
  );
}
