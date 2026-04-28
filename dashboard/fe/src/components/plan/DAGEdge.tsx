'use client';

import React from 'react';
import { DAGEdge as DAGEdgeType } from '@/types';

interface DAGEdgeProps {
  edge: DAGEdgeType;
  fromPos: { x: number; y: number };
  toPos: { x: number; y: number };
  mode?: 'live' | 'authoring';
  onDelete?: (from: string, to: string) => void;
}

export default function DAGEdge({ edge, fromPos, toPos, mode, onDelete }: DAGEdgeProps) {
  const { is_critical } = edge;
  
  // Calculate path — edges connect from right-center of source to left-center of target
  const NODE_W = 200;
  const NODE_H = 95;
  const x1 = fromPos.x + NODE_W;
  const y1 = fromPos.y + NODE_H / 2;
  const x2 = toPos.x;
  const y2 = toPos.y + NODE_H / 2;
  
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;

  // Cubic bezier control points for smooth horizontal curves
  const dx = Math.max(Math.abs(x2 - x1) * 0.4, 40);
  const pathD = `M ${x1},${y1} C ${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
  
  const strokeColor = is_critical ? '#2563eb' : '#94a3b8'; // primary-600 vs slate-400
  const strokeWidth = is_critical ? 3 : 1.5;
  const strokeDasharray = is_critical ? '0' : '5,5';

  return (
    <g className="group">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={strokeDasharray}
        markerEnd={`url(#arrowhead-${is_critical ? 'critical' : 'normal'})`}
        className="transition-all duration-300"
      />
      {/* Invisible thicker path for better hover area */}
      <path
        d={pathD}
        fill="none"
        stroke="transparent"
        strokeWidth={12}
        className="cursor-pointer"
      >
        <title>{`Dependency: ${edge.from} → ${edge.to}${is_critical ? ' (Critical Path)' : ''}`}</title>
      </path>

      {/* Delete button (only in authoring mode, visible on group hover) */}
      {mode === 'authoring' && (
        <g 
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.(edge.from, edge.to);
          }}
          className="cursor-pointer transition-all duration-200 opacity-0 group-hover:opacity-100"
        >
          <circle
            cx={midX}
            cy={midY}
            r="8"
            fill="#ef4444"
            className="shadow-sm hover:scale-110 transition-transform origin-center"
            style={{ transformOrigin: `${midX}px ${midY}px` }}
          />
          <text
            x={midX}
            y={midY}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            fontSize="10"
            fontWeight="bold"
            className="pointer-events-none"
          >
            ×
          </text>
        </g>
      )}
    </g>
  );
}
