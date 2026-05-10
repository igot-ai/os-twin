/**
 * EdgeLines — WebGL line segments for graph edges.
 *
 * Uses THREE.LineSegments with a BufferGeometry that's updated
 * every frame from the simulation node positions.
 *
 * Features:
 * - Per-edge color based on relationship type
 * - Path edges highlighted in gold
 * - Alpha based on edge weight and path membership
 */

import React, { useRef, useMemo } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import type { SimNode, SimLink } from './useForceSimulation';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface EdgeLinesProps {
  links: SimLink[];
  /** Selected path info (source, target, ordered path) */
  selectedPath: { source: string; target: string; path: string[] } | null;
}

// ---------------------------------------------------------------------------
// Vertex shader — passes per-vertex alpha to fragment
// ---------------------------------------------------------------------------

const vertexShader = /* glsl */ `
  attribute float aAlpha;
  varying float vAlpha;
  varying vec3 vColor;

  void main() {
    vAlpha = aAlpha;
    vColor = color;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  varying float vAlpha;
  varying vec3 vColor;

  void main() {
    gl_FragColor = vec4(vColor, vAlpha);
  }
`;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EdgeLines({ links, selectedPath }: EdgeLinesProps) {
  const linesRef = useRef<THREE.LineSegments>(null);

  const count = links.length;

  // ---- Create shader material ----
  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      vertexColors: true,
    });
  }, []);

  // ---- Create geometry with position + color + alpha buffers ----
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 2 * 3);
    const colors = new Float32Array(count * 2 * 3);
    const alphas = new Float32Array(count * 2);

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.setAttribute('aAlpha', new THREE.BufferAttribute(alphas, 1));

    return geo;
  }, [count]);

  // ---- Update positions, colors, and alphas every frame ----
  useFrame(() => {
    const lines = linesRef.current;
    if (!lines || count === 0) return;

    const posAttr = lines.geometry.getAttribute('position') as THREE.BufferAttribute;
    const colAttr = lines.geometry.getAttribute('color') as THREE.BufferAttribute;
    const alphaAttr = lines.geometry.getAttribute('aAlpha') as THREE.BufferAttribute;

    // Build set of path edges for fast lookup
    const pathEdgeSet = new Set<string>();
    if (selectedPath?.path && selectedPath.path.length > 1) {
      for (let i = 0; i < selectedPath.path.length - 1; i++) {
        pathEdgeSet.add(`${selectedPath.path[i]}->${selectedPath.path[i + 1]}`);
        pathEdgeSet.add(`${selectedPath.path[i + 1]}->${selectedPath.path[i]}`);
      }
    }

    for (let i = 0; i < count; i++) {
      const link = links[i];
      const source = link.source as SimNode;
      const target = link.target as SimNode;

      const sx = source.x ?? 0;
      const sy = -(source.y ?? 0);
      const sz = source.z ?? 0;
      const tx = target.x ?? 0;
      const ty = -(target.y ?? 0);
      const tz = target.z ?? 0;

      posAttr.setXYZ(i * 2, sx, sy, sz);
      posAttr.setXYZ(i * 2 + 1, tx, ty, tz);

      const edgeKey = `${source.id}->${target.id}`;
      const isPathEdge = pathEdgeSet.has(edgeKey);

      const c = new THREE.Color(link.color);
      const alpha = 0.15 + (link.weight ?? 1) * 0.15;

      if (isPathEdge) {
        const gold = new THREE.Color('#fbbf24');
        colAttr.setXYZ(i * 2, gold.r, gold.g, gold.b);
        colAttr.setXYZ(i * 2 + 1, gold.r, gold.g, gold.b);
        alphaAttr.setX(i * 2, 0.9);
        alphaAttr.setX(i * 2 + 1, 0.9);
      } else {
        colAttr.setXYZ(i * 2, c.r, c.g, c.b);
        colAttr.setXYZ(i * 2 + 1, c.r, c.g, c.b);
        alphaAttr.setX(i * 2, alpha);
        alphaAttr.setX(i * 2 + 1, alpha);
      }
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    alphaAttr.needsUpdate = true;

    lines.geometry.setDrawRange(0, count * 2);
  });

  if (count === 0) return null;

  return (
    <lineSegments ref={linesRef} geometry={geometry} material={material} frustumCulled={false} renderOrder={0} />
  );
}
