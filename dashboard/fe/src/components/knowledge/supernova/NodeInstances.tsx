/**
 * NodeInstances — WebGL instanced mesh for graph nodes.
 *
 * Renders nodes grouped by shape type (label-based geometry).
 * Each shape type gets its own InstancedMesh with a different geometry:
 *   sphere, octahedron, box, tetrahedron, dodecahedron, icosahedron
 *
 * Also renders glow halos (sphere) and selection rings (sphere)
 * as separate passes with their own InstancedMesh.
 *
 * Shader features:
 * - Brightness-based opacity (dim non-highlighted labels)
 * - Ignition glow
 * - Selection highlight
 * - Path highlight
 */

import React, { useRef, useMemo } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import type { SimNode } from './useForceSimulation';
import { SHAPE_TYPES } from '../constants';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface NodeInstancesProps {
  nodes: SimNode[];
  ignitionSet: Set<string>;
  selectedId: string | null;
  pathSet: Set<string>;
  onNodeClick: (nodeId: string) => void;
  highlightedLabels: Set<string>;
}

// ---------------------------------------------------------------------------
// Geometry factory — one geometry per shape type
// ---------------------------------------------------------------------------

function createGeometry(shapeType: number): THREE.BufferGeometry {
  switch (SHAPE_TYPES[shapeType]) {
    case 'octahedron':
      return new THREE.OctahedronGeometry(0.5, 0);
    case 'box':
      return new THREE.BoxGeometry(0.7, 0.7, 0.7);
    case 'tetrahedron':
      return new THREE.TetrahedronGeometry(0.6, 0);
    case 'dodecahedron':
      return new THREE.DodecahedronGeometry(0.5, 0);
    case 'icosahedron':
      return new THREE.IcosahedronGeometry(0.5, 0);
    case 'sphere':
    default:
      return new THREE.SphereGeometry(0.5, 12, 12);
  }
}

// ---------------------------------------------------------------------------
// Shaders — shared across all shape groups
// ---------------------------------------------------------------------------

const vertexShader = /* glsl */ `
  attribute float aBrightness;
  attribute float aIgnition;
  attribute float aSelected;
  attribute float aPathHighlight;
  attribute float aLabelDim;
  attribute vec3 aNodeColor;

  varying float vBrightness;
  varying float vIgnition;
  varying float vSelected;
  varying float vPathHighlight;
  varying float vLabelDim;
  varying vec3 vNodeColor;

  void main() {
    vBrightness = aBrightness;
    vIgnition = aIgnition;
    vSelected = aSelected;
    vPathHighlight = aPathHighlight;
    vLabelDim = aLabelDim;
    vNodeColor = aNodeColor;

    vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const fragmentShader = /* glsl */ `
  varying float vBrightness;
  varying float vIgnition;
  varying float vSelected;
  varying float vPathHighlight;
  varying float vLabelDim;
  varying vec3 vNodeColor;

  void main() {
    float alpha = mix(0.4, 1.0, vBrightness);

    // Dim non-highlighted labels
    alpha *= vLabelDim;

    vec3 color = vNodeColor;

    // Dim nodes: desaturate toward light gray
    if (vBrightness < 0.5) {
      vec3 gray = vec3(0.82);
      color = mix(gray, color, vBrightness * 2.0);
    }

    // Extra desaturation for label-dimmed nodes
    if (vLabelDim < 0.5) {
      vec3 gray = vec3(0.88);
      color = mix(gray, color, 0.3);
    }

    // Ignition glow — saturate and brighten
    if (vIgnition > 0.5) {
      color = mix(color, vec3(1.0), 0.2);
      alpha = 1.0;
    }

    // Selection highlight — whiten
    if (vSelected > 0.5) {
      color = mix(color, vec3(1.0), 0.5);
      alpha = 1.0;
    }

    // Path highlight — gold tint
    if (vPathHighlight > 0.5) {
      color = mix(color, vec3(0.85, 0.65, 0.1), 0.5);
      alpha = 1.0;
    }

    gl_FragColor = vec4(color, alpha);
  }
`;

const glowVertexShader = /* glsl */ `
  attribute float aIgnition;
  attribute vec3 aNodeColor;

  varying float vIgnition;
  varying vec3 vNodeColor;

  void main() {
    vIgnition = aIgnition;
    vNodeColor = aNodeColor;

    vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const glowFragmentShader = /* glsl */ `
  varying float vIgnition;
  varying vec3 vNodeColor;

  void main() {
    if (vIgnition < 0.5) discard;
    gl_FragColor = vec4(vNodeColor, 0.12);
  }
`;

const ringVertexShader = /* glsl */ `
  attribute float aSelected;
  attribute float aPathHighlight;
  attribute vec3 aNodeColor;

  varying float vSelected;
  varying float vPathHighlight;
  varying vec3 vNodeColor;

  void main() {
    vSelected = aSelected;
    vPathHighlight = aPathHighlight;
    vNodeColor = aNodeColor;

    vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const ringFragmentShader = /* glsl */ `
  varying float vSelected;
  varying float vPathHighlight;
  varying vec3 vNodeColor;

  void main() {
    if (vSelected < 0.5 && vPathHighlight < 0.5) discard;

    vec3 color = vSelected > 0.5 ? vNodeColor : vec3(0.85, 0.65, 0.1);
    float alpha = 0.5;

    gl_FragColor = vec4(color, alpha);
  }
`;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NodeInstances({
  nodes,
  ignitionSet,
  selectedId,
  pathSet,
  onNodeClick,
  highlightedLabels,
}: NodeInstancesProps) {
  const glowRef = useRef<THREE.InstancedMesh>(null);
  const ringRef = useRef<THREE.InstancedMesh>(null);
  const shapeRefs = useRef<(THREE.InstancedMesh | null)[]>([]);

  const count = nodes.length;
  const hasHighlight = highlightedLabels.size > 0;

  // ---- Group nodes by shape type ----
  const shapeGroups = useMemo(() => {
    const groups = new Map<number, SimNode[]>();
    for (const node of nodes) {
      const st = node.shapeType ?? 0;
      let group = groups.get(st);
      if (!group) {
        group = [];
        groups.set(st, group);
      }
      group.push(node);
    }
    return groups;
  }, [nodes]);

  // ---- Create materials ----
  const [nodeMaterial, glowMaterial, ringMaterial] = useMemo(() => [
    new THREE.ShaderMaterial({ vertexShader, fragmentShader, transparent: true, depthWrite: false }),
    new THREE.ShaderMaterial({ vertexShader: glowVertexShader, fragmentShader: glowFragmentShader, transparent: true, depthWrite: false }),
    new THREE.ShaderMaterial({ vertexShader: ringVertexShader, fragmentShader: ringFragmentShader, transparent: true, depthWrite: false }),
  ], []);

  // ---- Create per-shape geometries ----
  const shapeGeometries = useMemo(() => {
    return SHAPE_TYPES.map((_, i) => {
      const base = createGeometry(i);
      const instanced = new THREE.InstancedBufferGeometry().copy(
        base as unknown as THREE.InstancedBufferGeometry
      );
      return instanced;
    });
  }, []);

  // ---- Glow + ring geometries (always sphere) ----
  const glowGeo = useMemo(() => {
    const base = new THREE.SphereGeometry(0.5, 12, 12);
    const geo = new THREE.InstancedBufferGeometry().copy(base as unknown as THREE.InstancedBufferGeometry);
    return geo;
  }, []);

  const ringGeo = useMemo(() => {
    const base = new THREE.SphereGeometry(0.5, 12, 12);
    const geo = new THREE.InstancedBufferGeometry().copy(base as unknown as THREE.InstancedBufferGeometry);
    return geo;
  }, []);

  // ---- Update all instances every frame ----
  const dummy = useMemo(() => new THREE.Object3D(), []);

  useFrame(() => {
    if (count === 0) return;

    // Global index tracker for glow/ring (which span ALL nodes)
    let globalIdx = 0;

    // Per-instance attribute arrays for glow/ring (all nodes)
    const ignitionArr = new Float32Array(count);
    const selectedArr = new Float32Array(count);
    const pathArr = new Float32Array(count);
    const colorArr = new Float32Array(count * 3);

    for (const [shapeType, groupNodes] of shapeGroups) {
      const mesh = shapeRefs.current[shapeType];
      if (!mesh) continue;

      const geo = mesh.geometry as THREE.InstancedBufferGeometry;
      const groupCount = groupNodes.length;

      // Resize instance count
      geo.instanceCount = groupCount;

      // Ensure per-instance attributes
      let brightnessAttr = geo.getAttribute('aBrightness') as THREE.InstancedBufferAttribute | null;
      const needsCreate = !brightnessAttr || brightnessAttr.count !== groupCount;

      if (needsCreate) {
        brightnessAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount), 1);
        const labelDimAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount), 1);
        const gIgnitionAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount), 1);
        const gSelectedAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount), 1);
        const gPathAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount), 1);
        const gColorAttr = new THREE.InstancedBufferAttribute(new Float32Array(groupCount * 3), 3);

        geo.setAttribute('aBrightness', brightnessAttr);
        geo.setAttribute('aLabelDim', labelDimAttr);
        geo.setAttribute('aIgnition', gIgnitionAttr);
        geo.setAttribute('aSelected', gSelectedAttr);
        geo.setAttribute('aPathHighlight', gPathAttr);
        geo.setAttribute('aNodeColor', gColorAttr);
      }

      const labelDimAttr = geo.getAttribute('aLabelDim') as THREE.InstancedBufferAttribute;
      const gIgnAttr = geo.getAttribute('aIgnition') as THREE.InstancedBufferAttribute;
      const gSelAttr = geo.getAttribute('aSelected') as THREE.InstancedBufferAttribute;
      const gPathAttr = geo.getAttribute('aPathHighlight') as THREE.InstancedBufferAttribute;
      const gColorAttr = geo.getAttribute('aNodeColor') as THREE.InstancedBufferAttribute;

      for (let gi = 0; gi < groupCount; gi++) {
        const node = groupNodes[gi];
        const x = node.x ?? 0;
        const y = -(node.y ?? 0);
        const z = node.z ?? 0;
        const isSelected = selectedId === node.id;
        const baseScale = 4 + Math.pow(node.degree, 1.1) * 0.4 + Math.pow(node.score, 2) * 8;
        const scale = isSelected ? baseScale + 3 : baseScale;
        const isHighlighted = !hasHighlight || highlightedLabels.has(node.label);

        // Main mesh instance
        dummy.position.set(x, y, z);
        dummy.scale.set(scale, scale, scale);
        dummy.updateMatrix();
        mesh.setMatrixAt(gi, dummy.matrix);

        brightnessAttr!.setX(gi, node.brightness ?? 0.3);
        labelDimAttr.setX(gi, isHighlighted ? 1.0 : 0.15);
        gIgnAttr.setX(gi, ignitionSet.has(node.id) ? 1.0 : 0.0);
        gSelAttr.setX(gi, isSelected ? 1.0 : 0.0);
        gPathAttr.setX(gi, pathSet.has(node.id) ? 1.0 : 0.0);
        const c = new THREE.Color(node.color);
        gColorAttr.setXYZ(gi, c.r, c.g, c.b);

        // Glow/ring global index
        const glowScale = scale + 10;
        dummy.position.set(x, y, z);
        dummy.scale.set(glowScale, glowScale, glowScale);
        dummy.updateMatrix();
        glowRef.current?.setMatrixAt(globalIdx, dummy.matrix);

        const ringScale = isSelected ? scale + 6 : scale + 4;
        dummy.scale.set(ringScale, ringScale, ringScale);
        dummy.updateMatrix();
        ringRef.current?.setMatrixAt(globalIdx, dummy.matrix);

        ignitionArr[globalIdx] = ignitionSet.has(node.id) ? 1.0 : 0.0;
        selectedArr[globalIdx] = isSelected ? 1.0 : 0.0;
        pathArr[globalIdx] = pathSet.has(node.id) ? 1.0 : 0.0;
        colorArr[globalIdx * 3] = c.r;
        colorArr[globalIdx * 3 + 1] = c.g;
        colorArr[globalIdx * 3 + 2] = c.b;

        globalIdx++;
      }

      mesh.instanceMatrix.needsUpdate = true;
      brightnessAttr!.needsUpdate = true;
      labelDimAttr.needsUpdate = true;
      gIgnAttr.needsUpdate = true;
      gSelAttr.needsUpdate = true;
      gPathAttr.needsUpdate = true;
      gColorAttr.needsUpdate = true;
    }

    // Update glow + ring
    if (glowRef.current) {
      glowRef.current.instanceMatrix.needsUpdate = true;
      const gg = glowRef.current.geometry as THREE.InstancedBufferGeometry;
      gg.instanceCount = count;
      let gIgnAttr = gg.getAttribute('aIgnition') as THREE.InstancedBufferAttribute | null;
      let gColorAttr = gg.getAttribute('aNodeColor') as THREE.InstancedBufferAttribute | null;
      if (!gIgnAttr || gIgnAttr.count !== count) {
        gIgnAttr = new THREE.InstancedBufferAttribute(ignitionArr, 1);
        gColorAttr = new THREE.InstancedBufferAttribute(colorArr, 3);
        gg.setAttribute('aIgnition', gIgnAttr);
        gg.setAttribute('aNodeColor', gColorAttr);
      } else {
        gIgnAttr!.array.set(ignitionArr);
        gIgnAttr!.needsUpdate = true;
        gColorAttr!.array.set(colorArr);
        gColorAttr!.needsUpdate = true;
      }
    }

    if (ringRef.current) {
      ringRef.current.instanceMatrix.needsUpdate = true;
      const rg = ringRef.current.geometry as THREE.InstancedBufferGeometry;
      rg.instanceCount = count;
      let rSelAttr = rg.getAttribute('aSelected') as THREE.InstancedBufferAttribute | null;
      let rPathAttr = rg.getAttribute('aPathHighlight') as THREE.InstancedBufferAttribute | null;
      let rColorAttr = rg.getAttribute('aNodeColor') as THREE.InstancedBufferAttribute | null;
      if (!rSelAttr || rSelAttr.count !== count) {
        rSelAttr = new THREE.InstancedBufferAttribute(selectedArr, 1);
        rPathAttr = new THREE.InstancedBufferAttribute(pathArr, 1);
        rColorAttr = new THREE.InstancedBufferAttribute(colorArr, 3);
        rg.setAttribute('aSelected', rSelAttr);
        rg.setAttribute('aPathHighlight', rPathAttr);
        rg.setAttribute('aNodeColor', rColorAttr);
      } else {
        rSelAttr.array.set(selectedArr);
        rSelAttr.needsUpdate = true;
        rPathAttr!.array.set(pathArr);
        rPathAttr!.needsUpdate = true;
        rColorAttr!.array.set(colorArr);
        rColorAttr!.needsUpdate = true;
      }
    }
  });

  // ---- Click handler ----
  const handleClick = useMemo(() => {
    return (e: THREE.Event) => {
      const event = e as THREE.Event & { instanceId?: number; stopped?: boolean };
      if (event.instanceId != null) {
        for (const [, groupNodes] of shapeGroups) {
          if (event.instanceId < groupNodes.length) {
            const node = groupNodes[event.instanceId];
            if (node) onNodeClick(node.id);
            break;
          }
        }
        event.stopped = true;
      }
    };
  }, [shapeGroups, onNodeClick]);

  if (count === 0) return null;

  return (
    <group>
      {/* Glow layer */}
      <instancedMesh
        ref={glowRef}
        args={[glowGeo, glowMaterial, count]}
        frustumCulled={false}
        renderOrder={0}
      />

      {/* Ring layer */}
      <instancedMesh
        ref={ringRef}
        args={[ringGeo, ringMaterial, count]}
        frustumCulled={false}
        renderOrder={1}
      />

      {/* Per-shape node layers */}
      {SHAPE_TYPES.map((shapeName, shapeType) => {
        const groupNodes = shapeGroups.get(shapeType);
        if (!groupNodes || groupNodes.length === 0) return null;
        return (
          <instancedMesh
            key={shapeName}
            ref={el => { shapeRefs.current[shapeType] = el; }}
            args={[shapeGeometries[shapeType], nodeMaterial, groupNodes.length]}
            frustumCulled={false}
            renderOrder={2}
            onClick={handleClick}
          />
        );
      })}
    </group>
  );
}
