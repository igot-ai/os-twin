'use client';

import React, { useRef, useEffect, useState, useMemo } from 'react';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';
import { getNodeColor } from '../constants';

interface MinimapProps {
  nodes: ExplorerNode[];
  edges: ExplorerEdge[];
  selectedNodeId: string | null;
  ignitionPoints: string[];
  width?: number;
  height?: number;
}

export default function Minimap({
  nodes,
  edges,
  selectedNodeId,
  ignitionPoints,
  width = 140,
  height = 100,
}: MinimapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState(false);

  const bounds = useMemo(() => {
    if (nodes.length === 0) return null;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodes) {
      const x = (n.properties?.x as number) ?? 0;
      const y = (n.properties?.y as number) ?? 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    const pad = 20;
    return { minX: minX - pad, maxX: maxX + pad, minY: minY - pad, maxY: maxY + pad };
  }, [nodes]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !bounds) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    const scaleX = width / (bounds.maxX - bounds.minX);
    const scaleY = height / (bounds.maxY - bounds.minY);
    const scale = Math.min(scaleX, scaleY);
    const ox = (width - (bounds.maxX - bounds.minX) * scale) / 2;
    const oy = (height - (bounds.maxY - bounds.minY) * scale) / 2;

    const toX = (x: number) => (x - bounds.minX) * scale + ox;
    const toY = (y: number) => (y - bounds.minY) * scale + oy;

    const ignitionSet = new Set(ignitionPoints);

    // Edges
    ctx.strokeStyle = 'rgba(100, 116, 139, 0.15)';
    ctx.lineWidth = 0.5;
    for (const edge of edges) {
      const sNode = nodes.find(n => n.id === edge.source);
      const tNode = nodes.find(n => n.id === edge.target);
      if (!sNode || !tNode) continue;
      ctx.beginPath();
      ctx.moveTo(toX((sNode.properties?.x as number) ?? 0), toY((sNode.properties?.y as number) ?? 0));
      ctx.lineTo(toX((tNode.properties?.x as number) ?? 0), toY((tNode.properties?.y as number) ?? 0));
      ctx.stroke();
    }

    // Nodes
    for (const node of nodes) {
      const x = toX((node.properties?.x as number) ?? 0);
      const y = toY((node.properties?.y as number) ?? 0);
      const isIgnited = ignitionSet.has(node.id);
      const isSelected = node.id === selectedNodeId;
      const r = isSelected ? 3 : isIgnited ? 2 : 1;

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = isSelected
        ? '#ffffff'
        : isIgnited
          ? getNodeColor(node.label)
          : 'rgba(100, 116, 139, 0.4)';
      ctx.fill();
    }
  }, [nodes, edges, bounds, selectedNodeId, ignitionPoints, width, height]);

  if (nodes.length === 0) return null;

  return (
    <div
      className="absolute bottom-14 right-3 z-10 rounded-lg border overflow-hidden transition-opacity"
      style={{
        background: 'rgba(255, 255, 255, 0.85)',
        borderColor: 'var(--color-border)',
        opacity: hover ? 1 : 0.6,
        backdropFilter: 'blur(8px)',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <canvas ref={canvasRef} width={width} height={height} style={{ display: 'block' }} />
      <div
        className="px-1.5 py-0.5 text-[8px] text-center border-t"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-faint)' }}
      >
        {nodes.length} nodes
      </div>
    </div>
  );
}
