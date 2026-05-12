import React, { useRef, useEffect, useCallback } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { SimNode } from '../simulation/types';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';

interface CameraControllerProps {
  nodes: SimNode[];
  width: number;
  height: number;
  selectedId: string | null;
  is2D?: boolean;
  simGetIsRunning?: () => boolean;
}

const FOCUS_LERP = 0.06;

export default function CameraController({ nodes, width, height, selectedId, is2D = false, simGetIsRunning }: CameraControllerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const initialFitDone = useRef(false);
  const targetPosition = useRef<THREE.Vector3 | null>(null);
  const targetLookAt = useRef<THREE.Vector3>(new THREE.Vector3(0, 0, 0));
  const animating = useRef(false);
  const orthoConfigRef = useRef<{ left: number; right: number; top: number; bottom: number } | null>(null);

  const frameGraph = useCallback(() => {
    if (nodes.length === 0) return;

    let cx = 0, cy = 0, cz = 0;
    let count = 0;
    for (const n of nodes) {
      if (n.x != null && n.y != null && n.z != null) {
        cx += n.x;
        cy += n.y;
        cz += n.z;
        count++;
      }
    }
    if (count === 0) return;
    cx /= count;
    cy /= count;
    cz /= count;

    let varX = 0, varY = 0, varZ = 0;

    for (const n of nodes) {
      if (n.x != null && n.y != null && n.z != null) {
        const dx = n.x - cx;
        const dy = n.y - cy;
        const dz = n.z - cz;

        varX += dx ** 2;
        varY += dy ** 2;
        varZ += dz ** 2;
      }
    }

    const sigma = Math.sqrt(Math.max(varX, varY, varZ) / count);
    const radius = Math.max(3.0 * sigma, 250);

    const lookAtX = cx;
    const lookAtY = -cy;
    const lookAtZ = cz;

    if (is2D) {
      const aspect = width / height;
      const padding = 150;
      const extent = radius + padding;

      let orthoSize = extent;
      if (aspect < 1) {
        orthoSize = extent / aspect;
      }

      orthoConfigRef.current = {
        left: -orthoSize * aspect,
        right: orthoSize * aspect,
        top: orthoSize,
        bottom: -orthoSize,
      };
      targetPosition.current = new THREE.Vector3(lookAtX, lookAtY, 1000);
    } else {
      const fov = (camera as THREE.PerspectiveCamera).fov ?? 75;
      const fovRad = (fov * Math.PI) / 180;
      const dist = (radius + 200) / Math.sin(fovRad / 2);
      targetPosition.current = new THREE.Vector3(lookAtX, lookAtY, lookAtZ + dist);
    }

    targetLookAt.current.set(lookAtX, lookAtY, lookAtZ);

    if (controlsRef.current) {
      controlsRef.current.target.set(lookAtX, lookAtY, lookAtZ);
      controlsRef.current.update();
    }

    animating.current = true;
  }, [nodes, width, height, is2D, camera]);

  useEffect(() => {
    if (nodes.length === 0 || initialFitDone.current) return;
    initialFitDone.current = true;

    const timer = setTimeout(() => {
      frameGraph();
    }, 1500); // Give the 3D layout a bit more time to spread out on initial load

    return () => clearTimeout(timer);
  }, [nodes.length, frameGraph]);

  useEffect(() => {
    if (!selectedId) return;

    const node = nodes.find(n => n.id === selectedId);
    if (!node || node.x == null || node.y == null || node.z == null) return;

    const nx = node.x;
    const ny = -(node.y);
    const nz = node.z;
    const roleScale = node.roleScale ?? 1.0;
    
    const degree = node.degree ?? 0;
    const rawSize = degree > 0 ? degree * 10 : 5;
    const base = rawSize * 25;
    const scale = base * roleScale;
    const focusDist = is2D ? 0 : Math.max(40, scale * 6);

    if (is2D) {
      targetPosition.current = new THREE.Vector3(nx, ny, 1000);
    } else {
      const dir = new THREE.Vector3(nx, ny, nz);
      if (dir.length() < 0.001) dir.set(0, 0, 1);
      dir.normalize();
      targetPosition.current = new THREE.Vector3(
        nx + dir.x * focusDist,
        ny + dir.y * focusDist,
        nz + dir.z * focusDist
      );
    }
    targetLookAt.current.set(nx, ny, nz);

    if (controlsRef.current) {
      controlsRef.current.target.set(nx, ny, nz);
      controlsRef.current.update();
    }

    animating.current = true;
  }, [selectedId, nodes, is2D]);

  useFrame((state) => {
    if (is2D) {
      const orthoCam = state.camera as THREE.OrthographicCamera;
      if (orthoCam.isOrthographicCamera && orthoConfigRef.current) {
        const cfg = orthoConfigRef.current;
        orthoCam.left = cfg.left;
        orthoCam.right = cfg.right;
        orthoCam.top = cfg.top;
        orthoCam.bottom = cfg.bottom;
        orthoCam.updateProjectionMatrix();
        orthoConfigRef.current = null;
      }
    }

    if (animating.current && targetPosition.current) {
      state.camera.position.lerp(targetPosition.current, FOCUS_LERP);

      if (controlsRef.current) {
        controlsRef.current.target.lerp(targetLookAt.current, FOCUS_LERP);
        controlsRef.current.update();
      }

      if (state.camera.position.distanceTo(targetPosition.current) < 2) {
        animating.current = false;
      }
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableRotate={true}
      enablePan={true}
      enableZoom={true}
      enableDamping
      dampingFactor={0.15}
      minDistance={30}
      maxDistance={8000}
      zoomSpeed={0.8}
      panSpeed={0.8}
      rotateSpeed={0.5}
      mouseButtons={{
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
      }}
    />
  );
}
