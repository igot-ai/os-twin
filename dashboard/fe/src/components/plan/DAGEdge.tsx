'use client';

import React from 'react';
import { DAGEdge as DAGEdgeType } from '@/types';

interface DAGEdgeProps {
  edge: DAGEdgeType;
  fromPos: { x: number; y: number };
  toPos: { x: number; y: number };
}

export default function DAGEdge({ edge, fromPos, toPos }: DAGEdgeProps) {
  const { is_critical } = edge;
  
  // Calculate path
  // We'll use a simple straight line for now, or a slightly curved one.
  // Straight line for simplicity as per "simplified DAG".
  
  const strokeColor = is_critical ? '#2563eb' : '#94a3b8'; // primary-600 vs slate-400
  const strokeWidth = is_critical ? 3 : 1.5;
  const strokeDasharray = is_critical ? '0' : '5,5';

  return (
    <g className="group">
      <line
        x1={fromPos.x + 180} // assuming node width is 180, so from right edge
        y1={fromPos.y + 40}  // assuming node height is 80, so from middle
        x2={toPos.x}        // to left edge
        y2={toPos.y + 40}    // to middle
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={strokeDasharray}
        markerEnd={`url(#arrowhead-${is_critical ? 'critical' : 'normal'})`}
        className="transition-all duration-300"
      />
      {/* Invisible thicker line for better hover area */}
      <line
        x1={fromPos.x + 180}
        y1={fromPos.y + 40}
        x2={toPos.x}
        y2={toPos.y + 40}
        stroke="transparent"
        strokeWidth={10}
        className="cursor-help"
      >
        <title>{`Dependency: ${edge.from} → ${edge.to}${is_critical ? ' (Critical Path)' : ''}`}</title>
      </line>
    </g>
  );
}
