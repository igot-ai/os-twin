'use client';

import React, { useState, useCallback } from 'react';
import { QueryResultResponse } from '@/hooks/use-knowledge-query';
import { GraphNodeResponse, GraphEdgeResponse, GraphStatsResponse } from '@/hooks/use-knowledge-graph';
import GraphView from './GraphView';
import BacklinkBadge from './BacklinkBadge';

interface QueryPanelProps {
  selectedNamespace: string | null;
  queryResult: QueryResultResponse | null;
  isLoading: boolean;
  error: Error | null;
  graphNodes: GraphNodeResponse[];
  graphEdges: GraphEdgeResponse[];
  graphStats: GraphStatsResponse;
  graphLoading: boolean;
  onExecuteQuery: (query: string, mode: 'raw' | 'graph' | 'summarized', topK: number) => Promise<void>;
  onClearResult: () => void;
  onRefreshGraph: () => void;
  /** Callback when a memory note is clicked in the BacklinkBadge */
  onNoteClick?: (noteId: string) => void;
}

// Color palette for entity labels
const LABEL_COLORS: Record<string, string> = {
  entity: '#3b82f6',
  person: '#8b5cf6',
  organization: '#ec4899',
  location: '#f97316',
  event: '#10b981',
  concept: '#06b6d4',
  document: '#6366f1',
  default: '#6b7280',
};

function getNodeColor(label: string): string {
  return LABEL_COLORS[label.toLowerCase()] || LABEL_COLORS.default;
}

// Node detail drawer
function NodeDrawer({ node, onClose }: { node: GraphNodeResponse | null; onClose: () => void }) {
  if (!node) return null;

  const color = getNodeColor(node.label);

  return (
    <div 
      className="rounded-xl border p-4 mb-4"
      style={{ 
        background: 'var(--color-surface)', 
        borderColor: 'var(--color-border)' 
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span 
            className="w-3 h-3 rounded-full"
            style={{ background: color }}
          />
          <span 
            className="text-[10px] uppercase tracking-wide font-medium"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {node.label}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-hover transition-colors"
          aria-label="Close"
        >
          <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-text-muted)' }}>
            close
          </span>
        </button>
      </div>
      <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-main)' }}>
        {node.name}
      </h4>
      <div className="space-y-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex justify-between">
          <span>Score</span>
          <span className="font-medium" style={{ color: 'var(--color-text-main)' }}>
            {node.score.toFixed(2)}
          </span>
        </div>
        {node.properties && Object.keys(node.properties).length > 0 && (
          <div className="mt-2">
            <span className="font-medium">Properties</span>
            <pre 
              className="mt-1 p-2 rounded text-[10px] overflow-x-auto"
              style={{ background: 'var(--color-background)' }}
            >
              {JSON.stringify(node.properties, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// Results panel
function ResultsPanel({ 
  result, 
  mode, 
  onNoteClick 
}: { 
  result: QueryResultResponse; 
  mode: string;
  onNoteClick?: (noteId: string) => void;
}) {
  const hasWarning = result.warnings.includes('llm_unavailable');

  return (
    <div className="space-y-4">
      {/* Warning for LLM unavailable */}
      {hasWarning && mode === 'summarized' && (
        <div 
          className="p-3 rounded-lg text-sm flex items-start gap-2"
          style={{ 
            background: 'var(--color-warning-muted)', 
            color: 'var(--color-warning)' 
          }}
        >
          <span className="material-symbols-outlined text-[20px]">warning</span>
          <div>
            <p className="font-medium">LLM Not Configured</p>
            <p className="text-xs mt-0.5">Summarized mode requires an LLM. Results are from graph mode instead.</p>
          </div>
        </div>
      )}

      {/* Answer (for summarized mode) */}
      {result.answer && (
        <div 
          className="rounded-xl border p-4"
          style={{ 
            background: 'var(--color-surface)', 
            borderColor: 'var(--color-border)' 
          }}
        >
          <h4 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-muted)' }}>
            Answer
          </h4>
          <p className="text-sm" style={{ color: 'var(--color-text-main)' }}>
            {result.answer}
          </p>
        </div>
      )}

      {/* Chunks */}
      {result.chunks.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-muted)' }}>
            Relevant Chunks ({result.chunks.length})
          </h4>
          <div className="space-y-2">
            {result.chunks.slice(0, 5).map((chunk, i) => (
              <div 
                key={i}
                className="rounded-lg border p-3"
                style={{ 
                  background: 'var(--color-surface)', 
                  borderColor: 'var(--color-border)' 
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    {chunk.filename}
                  </span>
                  <div className="flex items-center gap-2">
                    {/* Memory backlink badge */}
                    {chunk.memory_links && chunk.memory_links.length > 0 && (
                      <BacklinkBadge
                        memoryLinks={chunk.memory_links}
                        namespace={result.namespace}
                        onNoteClick={onNoteClick}
                      />
                    )}
                    <span 
                      className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                      style={{ 
                        background: 'var(--color-primary-muted)', 
                        color: 'var(--color-primary)' 
                      }}
                    >
                      {chunk.score.toFixed(2)}
                    </span>
                  </div>
                </div>
                <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-main)' }}>
                  {chunk.text.slice(0, 300)}{chunk.text.length > 300 ? '...' : ''}
                </p>
              </div>
            ))}
            {result.chunks.length > 5 && (
              <p className="text-xs text-center" style={{ color: 'var(--color-text-muted)' }}>
                +{result.chunks.length - 5} more chunks
              </p>
            )}
          </div>
        </div>
      )}

      {/* Entities */}
      {result.entities.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--color-text-muted)' }}>
            Entities ({result.entities.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {result.entities.map((entity, i) => (
              <span 
                key={i}
                className="px-2 py-1 rounded-md text-xs font-medium"
                style={{ 
                  background: `${getNodeColor(entity.label)}20`, 
                  color: getNodeColor(entity.label),
                  border: `1px solid ${getNodeColor(entity.label)}40`
                }}
              >
                {entity.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Latency */}
      <div className="text-[10px] text-right" style={{ color: 'var(--color-text-faint)' }}>
        Query completed in {result.latency_ms}ms
      </div>
    </div>
  );
}

export default function QueryPanel({
  selectedNamespace,
  queryResult,
  isLoading,
  error,
  graphNodes,
  graphEdges,
  graphStats,
  graphLoading,
  onExecuteQuery,
  onClearResult,
  onRefreshGraph,
  onNoteClick,
}: QueryPanelProps) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'raw' | 'graph' | 'summarized'>('raw');
  const [topK, setTopK] = useState(10);
  const [selectedNode, setSelectedNode] = useState<GraphNodeResponse | null>(null);
  const [viewTab, setViewTab] = useState<'results' | 'graph'>('results');

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    await onExecuteQuery(query.trim(), mode, topK);
  }, [query, mode, topK, onExecuteQuery]);

  if (!selectedNamespace) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <span 
            className="material-symbols-outlined text-[48px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            search
          </span>
          <p className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
            Select a Namespace
          </p>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Choose a namespace to start querying your knowledge base.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Query form */}
      <form onSubmit={handleSubmit} className="p-4 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your query..."
            className="flex-1 px-3 py-2 rounded-lg border text-sm"
            style={{ 
              background: 'var(--color-background)', 
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-main)'
            }}
          />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-[16px]">
              {isLoading ? 'progress_activity' : 'search'}
            </span>
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Options row */}
        <div className="flex items-center gap-4">
          {/* Mode selector */}
          <div className="flex items-center gap-1.5">
            <label className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Mode
            </label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'raw' | 'graph' | 'summarized')}
              className="px-2 py-1 rounded border text-xs"
              style={{ 
                background: 'var(--color-background)', 
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-main)'
              }}
            >
              <option value="raw">Raw</option>
              <option value="graph">Graph</option>
              <option value="summarized">Summarized</option>
            </select>
          </div>

          {/* Top K slider */}
          <div className="flex items-center gap-1.5">
            <label className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Top K: {topK}
            </label>
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-20"
            />
          </div>

          {/* Clear button */}
          {queryResult && (
            <button
              type="button"
              onClick={onClearResult}
              className="ml-auto text-xs font-medium transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Clear
            </button>
          )}
        </div>
      </form>

      {/* Results area */}
      <div className="flex-1 overflow-hidden flex">
        {/* Main content */}
        <div className="flex-1 overflow-y-auto p-4" style={{ scrollbarWidth: 'thin' }}>
          {/* Error state */}
          {error && (
            <div 
              className="p-4 rounded-lg text-sm mb-4"
              style={{ 
                background: 'var(--color-danger-muted)', 
                color: 'var(--color-danger)' 
              }}
            >
              <p className="font-semibold mb-1">Query Error</p>
              <p>{error.message}</p>
            </div>
          )}

          {/* Results */}
          {queryResult ? (
            <ResultsPanel result={queryResult} mode={mode} onNoteClick={onNoteClick} />
          ) : (
            <div className="text-center py-8">
              <span 
                className="material-symbols-outlined text-[32px] mb-2"
                style={{ color: 'var(--color-text-muted)' }}
              >
                tips_and_updates
              </span>
              <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Enter a query to search your knowledge base.
              </p>
            </div>
          )}
        </div>

        {/* Graph panel (toggleable) */}
        <div 
          className="w-[400px] border-l flex flex-col"
          style={{ borderColor: 'var(--color-border)' }}
        >
          {/* Graph header */}
          <div className="flex items-center justify-between px-3 py-2 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
            <h4 className="text-xs font-semibold" style={{ color: 'var(--color-text-main)' }}>
              Knowledge Graph
            </h4>
            <button
              onClick={onRefreshGraph}
              className="p-1 rounded hover:bg-surface-hover transition-colors"
              aria-label="Refresh graph"
            >
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-text-muted)' }}>
                refresh
              </span>
            </button>
          </div>

          {/* Graph view */}
          <div className="flex-1 overflow-hidden">
            <GraphView
              nodes={graphNodes}
              edges={graphEdges}
              stats={graphStats}
              isLoading={graphLoading}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
            />
          </div>

          {/* Node detail drawer */}
          {selectedNode && (
            <div className="p-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
              <NodeDrawer node={selectedNode} onClose={() => setSelectedNode(null)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
