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
}: NodeLabelsProps) {
  const groupRef = useRef<THREE.Group>(null);
  const labelRefs = useRef<Map<string, THREE.Mesh>>(new Map());

  const visibleNodes = useMemo(() => {
    const sorted = [...nodes].sort((a, b) => {
      if (a.id === selectedId) return -1;
      if (b.id === selectedId) return 1;
      const aIgnited = ignitionSet.has(a.id);
      const bIgnited = ignitionSet.has(b.id);
      if (aIgnited && !bIgnited) return -1;
      if (!aIgnited && bIgnited) return 1;
      return b.score - a.score;
    });

    return sorted.slice(0, Math.min(maxLabels, MAX_LABELS));
  }, [nodes, ignitionSet, selectedId, maxLabels]);

  const labelEntries = useMemo(() => {
    const entries: LabelEntry[] = [];
    for (const node of visibleNodes) {
      const x = node.x ?? 0;
      const y = -(node.y ?? 0);
      const z = node.z ?? 0;
      const isIgnition = ignitionSet.has(node.id);
      const isSelected = node.id === selectedId;
      const label = node.name.length > 24 ? node.name.slice(0, 22) + '\u2026' : node.name;
      const color = isIgnition ? getNodeColor(node.label) : '#c8d2e6';
      const opacity = isSelected ? 1.0 : Math.max(nodeBrightness.get(node.id) ?? 0.3, 0.5);
      const baseOffset = 5 + Math.min(node.degree, 20) * 0.4 + node.score * 2;
      const yOffset = (baseOffset + (isSelected ? 4 : 0)) * 0.8;
      const fontSize = isSelected ? 13 : 9;

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
      const baseOffset = 5 + Math.min(node.degree, 20) * 0.4 + node.score * 2;
      const yOffset = (baseOffset + (isSelected ? 4 : 0)) * 0.8;

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
          outlineWidth={2}
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
