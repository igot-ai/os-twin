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
  const [isHovered, setIsHovered] = React.useState(false);
  
  // Calculate path
  const x1 = fromPos.x + 180;
  const y1 = fromPos.y + 40;
  const x2 = toPos.x;
  const y2 = toPos.y + 40;
  
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  
  const strokeColor = is_critical ? '#2563eb' : '#94a3b8'; // primary-600 vs slate-400
  const strokeWidth = is_critical ? 3 : 1.5;
  const strokeDasharray = is_critical ? '0' : '5,5';

  return (
    <g 
      className="group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={strokeDasharray}
        markerEnd={`url(#arrowhead-${is_critical ? 'critical' : 'normal'})`}
        className="transition-all duration-300"
      />
      {/* Invisible thicker line for better hover area */}
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke="transparent"
        strokeWidth={10}
        className="cursor-pointer"
      >
        <title>{`Dependency: ${edge.from} → ${edge.to}${is_critical ? ' (Critical Path)' : ''}`}</title>
      </line>

      {/* Delete button (only in authoring mode on hover) */}
      {mode === 'authoring' && isHovered && (
        <g 
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.(edge.from, edge.to);
          }}
          className="cursor-pointer hover:scale-110 transition-transform"
        >
          <circle
            cx={midX}
            cy={midY}
            r="8"
            fill="#ef4444"
            className="shadow-sm"
          />
          <text
            x={midX}
            y={midY}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            fontSize="10"
            fontWeight="bold"
            style={{ pointerEvents: 'none' }}
          >
            ×
          </text>
        </g>
      )}
    </g>
  );
}
