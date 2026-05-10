/**
 * CameraController — OrbitControls with zoom-to-fit for 3D sphere layout.
 *
 * - Left drag: rotate around the graph sphere
 * - Scroll: zoom in/out
 * - Right drag: pan
 * - Auto zoom-to-fit when data first loads
 */

import React, { useRef, useEffect } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { SimNode } from './useForceSimulation';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';

interface CameraControllerProps {
  nodes: SimNode[];
  width: number;
  height: number;
}

export default function CameraController({ nodes, width, height }: CameraControllerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const prevNodeCount = useRef(0);
  const targetPosition = useRef<THREE.Vector3 | null>(null);
  const animating = useRef(false);

  useEffect(() => {
    if (width > 0 && height > 0) {
      camera.position.set(0, 0, 600);
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
    }
  }, [camera, width, height]);

  useEffect(() => {
    if (nodes.length === 0 || nodes.length === prevNodeCount.current) return;
    prevNodeCount.current = nodes.length;

    const timer = setTimeout(() => {
      if (nodes.length === 0) return;

      let maxRadius = 0;
      for (const n of nodes) {
        if (n.x != null && n.y != null && n.z != null) {
          const dist = Math.sqrt(n.x * n.x + n.y * n.y + n.z * n.z);
          maxRadius = Math.max(maxRadius, dist);
        }
      }

      if (!isFinite(maxRadius) || maxRadius === 0) return;

      maxRadius += 80;

      const fov = (camera as THREE.PerspectiveCamera).fov ?? 75;
      const fovRad = (fov * Math.PI) / 180;
      const dist = maxRadius / Math.sin(fovRad / 2);

      targetPosition.current = new THREE.Vector3(0, 0, dist);
      animating.current = true;
    }, 800);

    return () => clearTimeout(timer);
  }, [nodes.length, nodes, camera]);

  useFrame(() => {
    if (!animating.current || !targetPosition.current) return;

    camera.position.lerp(targetPosition.current, 0.04);
    camera.lookAt(0, 0, 0);

    if (camera.position.distanceTo(targetPosition.current) < 1) {
      animating.current = false;
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enableRotate={true}
      enablePan={true}
      enableZoom={true}
      minDistance={30}
      maxDistance={8000}
      zoomSpeed={1.2}
      panSpeed={1.0}
      mouseButtons={{
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
      }}
    />
  );
}
