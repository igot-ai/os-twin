import React, { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { SimNode, SimLink } from '../simulation/types';
import { SHAPE_TYPES } from '../../constants';

const MAX_INSTANCES = 15000;
const EPS = 0.001;
const SIM_STEP_INTERVAL = 1;

interface NodeInstancesProps {
  nodes: SimNode[];
  ignitionSet: Set<string>;
  selectedId: string | null;
  pathSet: Set<string>;
  onNodeClick: (nodeId: string) => void;
  highlightedLabels: Set<string>;
  nodeBrightness: Map<string, number>;
  simStep: () => void;
  simGetPositions: () => { nodes: SimNode[]; links: SimLink[] };
  simGetIsRunning: () => boolean;
}

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
      return new THREE.SphereGeometry(0.5, 16, 16);
  }
}

function makeInstancedGeo(base: THREE.BufferGeometry): THREE.InstancedBufferGeometry {
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = base.index;
  geo.setAttribute('position', base.getAttribute('position'));
  if (base.getAttribute('normal')) geo.setAttribute('normal', base.getAttribute('normal'));

  geo.setAttribute('aNodeColor', new THREE.InstancedBufferAttribute(new Float32Array(MAX_INSTANCES * 3), 3));
  geo.setAttribute('aEmissiveColor', new THREE.InstancedBufferAttribute(new Float32Array(MAX_INSTANCES * 3), 3));
  geo.setAttribute('aEmissiveStrength', new THREE.InstancedBufferAttribute(new Float32Array(MAX_INSTANCES), 1));
  geo.setAttribute('aOpacity', new THREE.InstancedBufferAttribute(new Float32Array(MAX_INSTANCES), 1));
  geo.setAttribute('aHighlightDim', new THREE.InstancedBufferAttribute(new Float32Array(MAX_INSTANCES), 1));

  geo.instanceCount = 0;
  return geo;
}

const vertexShader = /* glsl */ `
  attribute vec3 aNodeColor;
  attribute vec3 aEmissiveColor;
  attribute float aEmissiveStrength;
  attribute float aOpacity;
  attribute float aHighlightDim;

  varying vec3 vColor;
  varying vec3 vEmissive;
  varying float vEmissiveStrength;
  varying float vOpacity;
  varying float vHighlightDim;
  varying vec3 vNormal;
  varying vec3 vWorldPos;

  void main() {
    vColor = aNodeColor;
    vEmissive = aEmissiveColor;
    vEmissiveStrength = aEmissiveStrength;
    vOpacity = aOpacity;
    vHighlightDim = aHighlightDim;

    vec4 worldPos = modelMatrix * instanceMatrix * vec4(position, 1.0);
    vWorldPos = worldPos.xyz;
    vNormal = normalize(mat3(modelMatrix) * mat3(instanceMatrix) * normal);

    gl_Position = projectionMatrix * viewMatrix * worldPos;
  }
`;

const fragmentShader = /* glsl */ `
  varying vec3 vColor;
  varying vec3 vEmissive;
  varying float vEmissiveStrength;
  varying float vOpacity;
  varying float vHighlightDim;
  varying vec3 vNormal;
  varying vec3 vWorldPos;

  void main() {
    vec3 N = normalize(vNormal);
    vec3 lightDir = normalize(vec3(0.3, 0.5, 1.0));
    float diff = max(dot(N, lightDir), 0.0);

    vec3 base = vColor * (0.35 + 0.65 * diff);
    vec3 emissive = vEmissive * vEmissiveStrength;
    vec3 color = base + emissive;

    float opacity = vOpacity * vHighlightDim;

    if (vHighlightDim < 0.5) {
      color = mix(vec3(0.08), color, 0.25);
    }

    gl_FragColor = vec4(color, opacity);
  }
`;

export default function NodeInstances({
  nodes,
  ignitionSet,
  selectedId,
  pathSet,
  onNodeClick,
  highlightedLabels,
  nodeBrightness,
  simStep,
  simGetIsRunning,
}: NodeInstancesProps) {
  const shapeRefs = useRef<(THREE.InstancedMesh | null)[]>([]);
  const selectionRef = useRef<THREE.Mesh | null>(null);
  const frameCountRef = useRef(0);
  const needsFinalRenderRef = useRef(false);

  const count = nodes.length;
  const hasHighlight = highlightedLabels.size > 0;

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

  const nodeMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: true,
    });
  }, []);

  const shapeGeometries = useMemo(() => {
    return SHAPE_TYPES.map((_, i) => makeInstancedGeo(createGeometry(i)));
  }, []);

  useEffect(() => {
    return () => {
      for (const geo of shapeGeometries) geo.dispose();
      nodeMaterial.dispose();
    };
  }, [shapeGeometries, nodeMaterial]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tempColor = useMemo(() => new THREE.Color(), []);

  useEffect(() => {
    if (count === 0) return;

    for (const [shapeType, groupNodes] of shapeGroups) {
      const mesh = shapeRefs.current[shapeType];
      if (!mesh) continue;

      const geo = mesh.geometry as THREE.InstancedBufferGeometry;
      const groupCount = Math.min(groupNodes.length, MAX_INSTANCES);
      geo.instanceCount = groupCount;

      const colorAttr = geo.getAttribute('aNodeColor') as THREE.InstancedBufferAttribute;
      const emissiveAttr = geo.getAttribute('aEmissiveColor') as THREE.InstancedBufferAttribute;
      const emissiveStrAttr = geo.getAttribute('aEmissiveStrength') as THREE.InstancedBufferAttribute;
      const opacityAttr = geo.getAttribute('aOpacity') as THREE.InstancedBufferAttribute;
      const highlightAttr = geo.getAttribute('aHighlightDim') as THREE.InstancedBufferAttribute;

      for (let gi = 0; gi < groupCount; gi++) {
        const node = groupNodes[gi];
        const isSelected = selectedId === node.id;
        const isIgnited = ignitionSet.has(node.id);
        const isOnPath = pathSet.has(node.id);
        const isHighlighted = !hasHighlight || highlightedLabels.has(node.label);

        tempColor.set(node.color);
        colorAttr.setXYZ(gi, tempColor.r, tempColor.g, tempColor.b);

        tempColor.set(node.emissiveColor ?? node.color);
        emissiveAttr.setXYZ(gi, tempColor.r, tempColor.g, tempColor.b);

        let emissiveStrength = node.emissiveStrength ?? 0.4;
        if (isIgnited) emissiveStrength *= 1.5;
        if (isSelected) emissiveStrength *= 2.0;
        if (isOnPath) emissiveStrength *= 1.8;
        emissiveStrAttr.setX(gi, emissiveStrength);

        let opacity = 0.4 + (nodeBrightness.get(node.id) ?? 0.3) * 0.6;
        if (isSelected || isIgnited || isOnPath) opacity = 1.0;
        opacityAttr.setX(gi, opacity);

        highlightAttr.setX(gi, isHighlighted ? 1.0 : 0.2);
      }

      colorAttr.needsUpdate = true;
      emissiveAttr.needsUpdate = true;
      emissiveStrAttr.needsUpdate = true;
      opacityAttr.needsUpdate = true;
      highlightAttr.needsUpdate = true;
    }
  }, [nodes, shapeGroups, selectedId, ignitionSet, pathSet, hasHighlight, highlightedLabels, count, nodeBrightness, tempColor]);

  useFrame(() => {
    const isRunning = simGetIsRunning();

    if (isRunning) {
      needsFinalRenderRef.current = true;
      frameCountRef.current++;
      if (frameCountRef.current % SIM_STEP_INTERVAL !== 0) return;
      simStep();
    } else {
      if (!needsFinalRenderRef.current) return;
      needsFinalRenderRef.current = false;
    }

    for (const [shapeType, groupNodes] of shapeGroups) {
      const mesh = shapeRefs.current[shapeType];
      if (!mesh) continue;

      const groupCount = Math.min(groupNodes.length, MAX_INSTANCES);
      if (groupCount === 0) continue;

      for (let gi = 0; gi < groupCount; gi++) {
        const node = groupNodes[gi];

        const x = node.x ?? 0;
        const y = -(node.y ?? 0);
        const z = node.z ?? 0;
        const roleScale = node.roleScale ?? 1.0;
        const isSelected = selectedId === node.id;
        const degree = node.degree ?? 0;
        // Size proportional to degree (20 edges is 4x bigger than 5 edges).
        // Base unit is 10, then scaled by 25x.
        const rawSize = degree > 0 ? degree * 10 : 5;
        const base = rawSize * 25;
        const scale = Math.max(EPS, base * roleScale * (isSelected ? 1.15 : 1.0));

        dummy.position.set(x, y, z);
        dummy.scale.set(scale, scale, scale);
        dummy.updateMatrix();
        mesh.setMatrixAt(gi, dummy.matrix);
      }

      mesh.instanceMatrix.needsUpdate = true;
    }
  });

  const selectedNode = useMemo(() => {
    if (!selectedId) return null;
    return nodes.find(n => n.id === selectedId) ?? null;
  }, [selectedId, nodes]);

  const selectionTransform = useMemo(() => {
    if (!selectedNode) return null;
    const x = selectedNode.x ?? 0;
    const y = -(selectedNode.y ?? 0);
    const z = selectedNode.z ?? 0;
    const roleScale = selectedNode.roleScale ?? 1.0;
    const degree = selectedNode.degree ?? 0;
    // Match the 25x proportional scale for the selection ring
    const rawSize = degree > 0 ? degree * 10 : 5;
    const base = rawSize * 25;
    const scale = Math.max(EPS, base * roleScale * 1.15 * 1.3);
    return { position: new THREE.Vector3(x, y, z), scale };
  }, [selectedNode]);

  const handleClick = useMemo(() => {
    return (e: THREE.Event & { instanceId?: number; stopped?: boolean; object?: THREE.Object3D }, shapeType: number) => {
      if (e.instanceId == null) return;
      const groupNodes = shapeGroups.get(shapeType);
      if (!groupNodes) return;
      const node = groupNodes[e.instanceId];
      if (node) onNodeClick(node.id);
      if ('stopPropagation' in e && typeof e.stopPropagation === 'function') {
        e.stopPropagation();
      }
      e.stopped = true;
    };
  }, [shapeGroups, onNodeClick]);

  if (count === 0) return null;

  return (
    <group>
      {SHAPE_TYPES.map((shapeName, shapeType) => {
        const groupNodes = shapeGroups.get(shapeType);
        if (!groupNodes || groupNodes.length === 0) return null;
        return (
          <instancedMesh
            key={shapeName}
            ref={el => {
              if (el) {
                shapeRefs.current[shapeType] = el;
                // Assign a massive bounding sphere so the raycaster doesn't ignore moving instances
                if (!el.boundingSphere) {
                  el.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1000000);
                }
              }
            }}
            args={[shapeGeometries[shapeType], nodeMaterial, Math.min(groupNodes.length, MAX_INSTANCES)]}
            frustumCulled={false}
            renderOrder={1}
            onClick={(e) => handleClick(e as THREE.Event & { instanceId?: number; stopped?: boolean; object?: THREE.Object3D }, shapeType)}
          />
        );
      })}

      {selectionTransform && (
        <mesh
          ref={selectionRef}
          position={selectionTransform.position}
          scale={selectionTransform.scale}
        >
          <ringGeometry args={[0.85, 1.0, 32]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.6} side={THREE.DoubleSide} depthTest={false} />
        </mesh>
      )}
    </group>
  );
}
