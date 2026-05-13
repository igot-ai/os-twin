import React, { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { SimNode, SimLink } from '../simulation/types';

const _pathColor = new THREE.Color('#fbbf24');
const _dimColor = new THREE.Color('#2a2a3a');
const _srcColor = new THREE.Color();
const _tgtColor = new THREE.Color();
const _dimLerp = new THREE.Color();

interface EdgeLinesProps {
  links: SimLink[];
  nodes: SimNode[];
  selectedPath: { source: string; target: string; path: string[] } | null;
  ignitionSet: Set<string>;
  highlightedEdges?: Set<string>;
  highlightedLabels?: Set<string>;
  simGetIsRunning: () => boolean;
}

export default function EdgeLines({ links, nodes, selectedPath, ignitionSet, highlightedEdges, highlightedLabels, simGetIsRunning }: EdgeLinesProps) {
  const linesRef = useRef<THREE.LineSegments>(null);
  const count = links.length;

  const maxVertices = Math.max(count * 2, 2);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(maxVertices * 3), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(maxVertices * 3), 3));
    geo.setDrawRange(0, 0);
    return geo;
  }, [maxVertices]);

  const material = useMemo(() => {
    return new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
      linewidth: 1,
    });
  }, []);

  const pathEdgeSet = useMemo(() => {
    const set = new Set<string>();
    if (selectedPath?.path && selectedPath.path.length > 1) {
      for (let i = 0; i < selectedPath.path.length - 1; i++) {
        set.add(`${selectedPath.path[i]}->${selectedPath.path[i + 1]}`);
        set.add(`${selectedPath.path[i + 1]}->${selectedPath.path[i]}`);
      }
    }
    return set;
  }, [selectedPath]);

  const nodeMap = useMemo(() => {
    const map = new Map<string, SimNode>();
    for (let i = 0; i < nodes.length; i++) {
      map.set(nodes[i].id, nodes[i]);
    }
    return map;
  }, [nodes]);

  const frameCountRef = useRef(0);
  const needsFinalRenderRef = useRef(false);

  useFrame(() => {
    const isRunning = simGetIsRunning();

    if (isRunning) {
      needsFinalRenderRef.current = true;
      frameCountRef.current++;
      if (frameCountRef.current % 4 !== 0) return;
    } else {
      if (!needsFinalRenderRef.current) return;
      needsFinalRenderRef.current = false;
    }

    const lines = linesRef.current;
    if (!lines || count === 0) return;

    const posAttr = lines.geometry.getAttribute('position') as THREE.BufferAttribute;

    for (let i = 0; i < count; i++) {
      const link = links[i];
      const srcId = typeof link.source === 'string' ? link.source : (link.source as SimNode).id;
      const tgtId = typeof link.target === 'string' ? link.target : (link.target as SimNode).id;

      const source = nodeMap.get(srcId);
      const target = nodeMap.get(tgtId);

      const sx = source?.x ?? 0;
      const sy = -(source?.y ?? 0);
      const sz = source?.z ?? 0;
      const tx = target?.x ?? 0;
      const ty = -(target?.y ?? 0);
      const tz = target?.z ?? 0;

      const vi = i * 2;
      posAttr.setXYZ(vi, sx, sy, sz);
      posAttr.setXYZ(vi + 1, tx, ty, tz);
    }

    posAttr.needsUpdate = true;
  });

  useEffect(() => {
    const lines = linesRef.current;
    if (!lines || count === 0) {
      if (lines) lines.geometry.setDrawRange(0, 0);
      return;
    }

    const posAttr = lines.geometry.getAttribute('position') as THREE.BufferAttribute;

    for (let i = 0; i < count; i++) {
      const link = links[i];
      const srcId = typeof link.source === 'string' ? link.source : (link.source as SimNode).id;
      const tgtId = typeof link.target === 'string' ? link.target : (link.target as SimNode).id;

      const source = nodeMap.get(srcId);
      const target = nodeMap.get(tgtId);

      const sx = source?.x ?? 0;
      const sy = -(source?.y ?? 0);
      const sz = source?.z ?? 0;
      const tx = target?.x ?? 0;
      const ty = -(target?.y ?? 0);
      const tz = target?.z ?? 0;

      const vi = i * 2;
      posAttr.setXYZ(vi, sx, sy, sz);
      posAttr.setXYZ(vi + 1, tx, ty, tz);
    }

    posAttr.needsUpdate = true;
    lines.geometry.setDrawRange(0, count * 2);
  }, [links, count, nodeMap]);

  useEffect(() => {
    const lines = linesRef.current;
    if (!lines || count === 0) return;

    const colAttr = lines.geometry.getAttribute('color') as THREE.BufferAttribute;

    const time = performance.now() * 0.001; // elapsed time in seconds

    for (let i = 0; i < count; i++) {
      const link = links[i];
      const srcId = typeof link.source === 'string' ? link.source : (link.source as SimNode).id;
      const tgtId = typeof link.target === 'string' ? link.target : (link.target as SimNode).id;

      const sourceNode = nodeMap.get(srcId);
      const targetNode = nodeMap.get(tgtId);

      const edgeKey = `${srcId}->${tgtId}`;
      const isPathEdge = pathEdgeSet.has(edgeKey);
      const connectsIgnited = ignitionSet.has(srcId) || ignitionSet.has(tgtId);
      const isEdgeHighlighted = highlightedEdges && highlightedEdges.size > 0 ? highlightedEdges.has(link.label || '') : false;
      const isFilteringEdges = highlightedEdges && highlightedEdges.size > 0;

      const sourceLabel = sourceNode?.label || '';
      const targetLabel = targetNode?.label || '';
      const isLabelHighlighted = highlightedLabels && highlightedLabels.size > 0
        ? (highlightedLabels.has(sourceLabel) || highlightedLabels.has(targetLabel))
        : false;
      const isFilteringLabels = highlightedLabels && highlightedLabels.size > 0;

      const vi = i * 2;

      if (isPathEdge) {
        _srcColor.set(link.color).lerp(_pathColor, 0.7);
        _tgtColor.set(link.color).lerp(_pathColor, 0.7);
        colAttr.setXYZ(vi, _srcColor.r, _srcColor.g, _srcColor.b);
        colAttr.setXYZ(vi + 1, _tgtColor.r, _tgtColor.g, _tgtColor.b);
      } else if (isFilteringEdges && isEdgeHighlighted) {
        // Create an animated directional pulse effect
        // We use Math.sin on time mixed with the edge index to make it feel like energy flowing
        const pulse = (Math.sin(time * 6 + i * 0.1) + 1) * 0.5; // 0 to 1
        _srcColor.set(link.color);
        _tgtColor.set(link.color).lerp(_pathColor, pulse * 0.6); // pulse towards an energy color at the target
        colAttr.setXYZ(vi, _srcColor.r * (1 + pulse), _srcColor.g * (1 + pulse), _srcColor.b * (1 + pulse));
        colAttr.setXYZ(vi + 1, _tgtColor.r * (1 + pulse), _tgtColor.g * (1 + pulse), _tgtColor.b * (1 + pulse));
      } else if (isFilteringLabels && isLabelHighlighted && !isFilteringEdges) {
        // When labels are filtered but NO edge filter is active, highlight edges connected to the selected labels
        const pulse = (Math.sin(time * 4 + i * 0.1) + 1) * 0.5;
        _srcColor.set(link.color);
        _tgtColor.set(link.color).lerp(new THREE.Color('#ffffff'), pulse * 0.4);
        colAttr.setXYZ(vi, _srcColor.r * (1 + pulse * 0.5), _srcColor.g * (1 + pulse * 0.5), _srcColor.b * (1 + pulse * 0.5));
        colAttr.setXYZ(vi + 1, _tgtColor.r * (1 + pulse * 0.5), _tgtColor.g * (1 + pulse * 0.5), _tgtColor.b * (1 + pulse * 0.5));
      } else if (connectsIgnited) {
        _srcColor.set(link.color);
        colAttr.setXYZ(vi, _srcColor.r * 1.5, _srcColor.g * 1.5, _srcColor.b * 1.5);
        colAttr.setXYZ(vi + 1, _srcColor.r * 1.5, _srcColor.g * 1.5, _srcColor.b * 1.5);
      } else if ((isFilteringEdges && !isEdgeHighlighted) || (isFilteringLabels && !isLabelHighlighted)) {
        _dimLerp.copy(_dimColor).lerp(_srcColor.set(link.color), 0.05); // Severely dim unhighlighted edges
        colAttr.setXYZ(vi, _dimLerp.r, _dimLerp.g, _dimLerp.b);
        colAttr.setXYZ(vi + 1, _dimLerp.r, _dimLerp.g, _dimLerp.b);
      } else {
        _dimLerp.copy(_dimColor).lerp(_srcColor.set(link.color), 0.25 + (link.weight ?? 1) * 0.1);
        colAttr.setXYZ(vi, _dimLerp.r, _dimLerp.g, _dimLerp.b);
        colAttr.setXYZ(vi + 1, _dimLerp.r, _dimLerp.g, _dimLerp.b);
      }
    }

    colAttr.needsUpdate = true;
  }, [links, count, pathEdgeSet, ignitionSet, highlightedEdges, highlightedLabels, nodeMap]);

  if (count === 0) return null;

  return (
    <lineSegments ref={linesRef} geometry={geometry} material={material} frustumCulled={false} renderOrder={0} />
  );
}
