import React, { useRef, useEffect } from 'react';
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

export default function CameraController({ nodes, width, height, selectedId, is2D = true, simGetIsRunning }: CameraControllerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const prevNodeCount = useRef(0);
  const targetPosition = useRef<THREE.Vector3 | null>(null);
  const targetLookAt = useRef<THREE.Vector3>(new THREE.Vector3(0, 0, 0));
  const animating = useRef(false);
  const orthoConfigRef = useRef<{ left: number; right: number; top: number; bottom: number } | null>(null);
  const wasRunningRef = useRef(false);

  useEffect(() => {
    if (width > 0 && height > 0 && is2D) {
      const aspect = width / height;
      const viewSize = 600;
      orthoConfigRef.current = {
        left: -viewSize * aspect,
        right: viewSize * aspect,
        top: viewSize,
        bottom: -viewSize,
      };
    }
  }, [width, height, is2D]);

  const frameGraph = () => {
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
    
    const sigma = Math.sqrt(Math.max(varX, varY, is2D ? 0 : varZ) / count);
    // Use 2.5 sigma to frame the vast majority of the graph, plus generous padding
    const radius = Math.max(3.0 * sigma, 250);

    const lookAtY = -cy;
    const lookAtX = cx;
    const lookAtZ = is2D ? 0 : cz;

    if (is2D) {
      const aspect = width / height;
      const padding = 150;
      const extent = radius + padding;
      
      // Ensure both horizontal and vertical extents fit inside the camera view
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
      const dist = (radius + 100) / Math.sin(fovRad / 2);
      targetPosition.current = new THREE.Vector3(lookAtX, lookAtY, lookAtZ + dist);
    }

    targetLookAt.current.set(lookAtX, lookAtY, lookAtZ);
    animating.current = true;
  };

  useEffect(() => {
    if (nodes.length === 0 || nodes.length === prevNodeCount.current) return;
    prevNodeCount.current = nodes.length;

    const timer = setTimeout(() => {
      frameGraph();
    }, 800);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, nodes, camera, is2D, width, height]);

  useEffect(() => {
    if (!selectedId) return;

    const node = nodes.find(n => n.id === selectedId);
    if (!node || node.x == null || node.y == null || node.z == null) return;

    const nx = node.x;
    const ny = -(node.y);
    const nz = is2D ? 0 : node.z;
    const roleScale = node.roleScale ?? 1.0;
    const base = 4 + Math.log2(node.degree + 1) * 3 + Math.pow(node.score, 2) * 6;
    const scale = base * roleScale;
    const focusDist = is2D ? 0 : Math.max(20, scale * 6);

    if (is2D) {
      targetPosition.current = new THREE.Vector3(nx, ny, 1000);
    } else {
      const dir = new THREE.Vector3(nx, ny, nz).normalize();
      if (dir.length() < 0.001) dir.set(0, 0, 1);
      targetPosition.current = new THREE.Vector3(
        nx + dir.x * focusDist,
        ny + dir.y * focusDist,
        nz + dir.z * focusDist
      );
    }
    targetLookAt.current.set(nx, ny, nz);
    animating.current = true;
  }, [selectedId, nodes, camera, is2D]);

  useFrame((state) => {
    if (simGetIsRunning) {
      const isRunning = simGetIsRunning();
      if (wasRunningRef.current && !isRunning) {
        // Simulation just stopped (converged). Re-frame the camera to show everything!
        frameGraph();
      }
      wasRunningRef.current = isRunning;
    }

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
      const currentLookAt = new THREE.Vector3();
      state.camera.getWorldDirection(currentLookAt);
      const targetDir = new THREE.Vector3().subVectors(targetLookAt.current, state.camera.position).normalize();
      currentLookAt.lerp(targetDir, FOCUS_LERP);
      state.camera.lookAt(
        state.camera.position.x + currentLookAt.x,
        state.camera.position.y + currentLookAt.y,
        state.camera.position.z + currentLookAt.z
      );

      if (state.camera.position.distanceTo(targetPosition.current) < 1) {
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
      dampingFactor={0.1}
      minDistance={30}
      maxDistance={8000}
      zoomSpeed={1.2}
      panSpeed={1.0}
      mouseButtons={{
        LEFT: is2D ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: is2D ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN,
      }}
    />
  );
}
