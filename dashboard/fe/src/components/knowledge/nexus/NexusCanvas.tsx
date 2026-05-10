'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';

const GraphScene = dynamic(() => import('../supernova/GraphScene'), { ssr: false });

interface NexusCanvasProps {
  nodes: ExplorerNode[];
  edges: ExplorerEdge[];
  isLoading: boolean;
  selectedNode: ExplorerNode | null;
  onSelectNode: (node: ExplorerNode | null) => void;
  onIgnite: (nodeId: string) => void;
  nodeBrightness: Map<string, number>;
  activeIgnitionPoints: string[];
  selectedPath: { source: string; target: string; path: string[] } | null;
}

export default function NexusCanvas(props: NexusCanvasProps) {
  return (
    <div className="absolute inset-0">
      <GraphScene
        nodes={props.nodes}
        edges={props.edges}
        isLoading={props.isLoading}
        selectedNode={props.selectedNode}
        onSelectNode={props.onSelectNode}
        onIgnite={props.onIgnite}
        nodeBrightness={props.nodeBrightness}
        activeIgnitionPoints={props.activeIgnitionPoints}
        selectedPath={props.selectedPath}
      />
    </div>
  );
}
