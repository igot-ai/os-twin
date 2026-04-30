'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet } from '@/lib/api-client';

interface MetricsData {
  timestamp: string;
  backend: string;
  counters: Record<string, { value: number; description: string; labels?: Record<string, number> }>;
  histograms: Record<string, { stats: { count: number; sum: number; min: number; max: number; avg: number }; description: string }>;
  gauges: Record<string, { value: number; description: string; labels?: Record<string, number> }>;
}

interface MetricsStripProps {
  refreshInterval?: number; // milliseconds, default 5000
  className?: string;
}

// Format bytes to human-readable
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Simple sparkline component
function Sparkline({ data, width = 60, height = 20, color = '#3b82f6' }: { 
  data: number[]; 
  width?: number; 
  height?: number; 
  color?: string;
}) {
  if (data.length < 2) {
    return (
      <div 
        className="flex items-center justify-center text-xs"
        style={{ width, height, color: 'var(--color-text-muted)' }}
      >
        —
      </div>
    );
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  
  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  );
}

// Progress bar component
function StorageBar({ bytes, maxBytes, label }: { bytes: number; maxBytes: number; label: string }) {
  const percentage = maxBytes > 0 ? (bytes / maxBytes) * 100 : 0;
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
        <span style={{ color: 'var(--color-text-main)' }}>{formatBytes(bytes)}</span>
      </div>
      <div 
        className="h-1.5 rounded-full overflow-hidden"
        style={{ background: 'var(--color-border)' }}
      >
        <div 
          className="h-full rounded-full transition-all duration-300"
          style={{ 
            width: `${Math.min(percentage, 100)}%`,
            background: percentage > 80 ? '#ef4444' : percentage > 60 ? '#f59e0b' : 'var(--color-primary)'
          }}
        />
      </div>
    </div>
  );
}

export default function MetricsStrip({ refreshInterval = 5000, className = '' }: MetricsStripProps) {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Query rate history (last 10 samples)
  const [queryRateHistory, setQueryRateHistory] = useState<number[]>([]);
  const [ingestRateHistory, setIngestRateHistory] = useState<number[]>([]);
  const [errorRateHistory, setErrorRateHistory] = useState<number[]>([]);
  // Use refs for accumulators so fetchMetrics stays stable across renders
  const lastQueryTotalRef = useRef(0);
  const lastIngestTotalRef = useRef(0);
  const lastErrorTotalRef = useRef(0);

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await apiGet<MetricsData>('/knowledge/metrics');
      setMetrics(data);
      setError(null);
      
      // Calculate rates based on counter changes
      const queryTotal = data.counters?.query_total?.value || 0;
      const ingestTotal = data.counters?.ingest_files_total?.value || 0;
      const errorTotal = (data.counters?.query_errors_total?.value || 0) + (data.counters?.llm_errors_total?.value || 0);
      
      // Calculate delta (rate per interval)
      const queryDelta = queryTotal - lastQueryTotalRef.current;
      const ingestDelta = ingestTotal - lastIngestTotalRef.current;
      const errorDelta = errorTotal - lastErrorTotalRef.current;
      
      lastQueryTotalRef.current = queryTotal;
      lastIngestTotalRef.current = ingestTotal;
      lastErrorTotalRef.current = errorTotal;
      
      // Update history (keep last 10)
      setQueryRateHistory(prev => [...prev.slice(-9), Math.max(0, queryDelta)]);
      setIngestRateHistory(prev => [...prev.slice(-9), Math.max(0, ingestDelta)]);
      setErrorRateHistory(prev => [...prev.slice(-9), Math.max(0, errorDelta)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [fetchMetrics, refreshInterval]);

  if (isLoading) {
    return (
      <div className={`p-3 rounded-lg ${className}`} style={{ background: 'var(--color-surface)' }}>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" 
            style={{ borderColor: 'var(--color-border)', borderTopColor: 'transparent' }} />
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Loading metrics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-3 rounded-lg ${className}`} style={{ background: 'var(--color-surface)' }}>
        <div className="text-xs" style={{ color: '#ef4444' }}>
          <span className="material-symbols-outlined text-sm align-middle mr-1">error</span>
          {error}
        </div>
      </div>
    );
  }

  if (!metrics) {
    return null;
  }

  // Extract metrics
  const queryTotal = metrics.counters?.query_total?.value || 0;
  const ingestFilesTotal = metrics.counters?.ingest_files_total?.value || 0;
  const ingestBytesTotal = metrics.counters?.ingest_bytes_total?.value || 0;
  const queryErrors = metrics.counters?.query_errors_total?.value || 0;
  const llmCalls = metrics.counters?.llm_calls_total?.value || 0;
  const namespacesTotal = metrics.gauges?.namespaces_total?.value || 0;
  
  // Per-namespace storage
  const diskBytesPerNs = metrics.gauges?.disk_bytes_per_namespace?.labels || {};
  
  // Query latency
  const queryLatencyStats = metrics.histograms?.query_latency_seconds?.stats;
  const avgQueryLatency = queryLatencyStats?.avg ? (queryLatencyStats.avg * 1000).toFixed(1) : '—';

  // Get namespace storage values for bar chart
  const namespaceStorages = Object.entries(diskBytesPerNs).map(([label, bytes]) => {
    const nsName = label.split('=')[1] || label;
    return { name: nsName, bytes };
  }).sort((a, b) => b.bytes - a.bytes).slice(0, 5);
  
  const maxStorage = Math.max(...namespaceStorages.map(ns => ns.bytes), 1);

  return (
    <div className={`p-3 rounded-lg space-y-3 ${className}`} style={{ background: 'var(--color-surface)' }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium" style={{ color: 'var(--color-text-main)' }}>
          Metrics
        </h3>
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Backend: {metrics.backend}
        </span>
      </div>

      {/* Sparklines row */}
      <div className="grid grid-cols-3 gap-4">
        {/* Query rate */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Query Rate</span>
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-main)' }}>
              {queryTotal.toLocaleString()}
            </span>
          </div>
          <Sparkline data={queryRateHistory} color="#3b82f6" />
        </div>

        {/* Ingest throughput */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Ingest Rate</span>
            <span className="text-xs font-medium" style={{ color: 'var(--color-text-main)' }}>
              {formatBytes(ingestBytesTotal)}
            </span>
          </div>
          <Sparkline data={ingestRateHistory} color="#10b981" />
        </div>

        {/* Error rate */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Error Rate</span>
            <span className="text-xs font-medium" style={{ color: queryErrors > 0 ? '#ef4444' : 'var(--color-text-main)' }}>
              {queryErrors}
            </span>
          </div>
          <Sparkline data={errorRateHistory} color="#ef4444" />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="p-2 rounded" style={{ background: 'var(--color-background)' }}>
          <div style={{ color: 'var(--color-text-muted)' }}>Namespaces</div>
          <div className="font-medium" style={{ color: 'var(--color-text-main)' }}>{namespacesTotal}</div>
        </div>
        <div className="p-2 rounded" style={{ background: 'var(--color-background)' }}>
          <div style={{ color: 'var(--color-text-muted)' }}>Files Ingested</div>
          <div className="font-medium" style={{ color: 'var(--color-text-main)' }}>{ingestFilesTotal.toLocaleString()}</div>
        </div>
        <div className="p-2 rounded" style={{ background: 'var(--color-background)' }}>
          <div style={{ color: 'var(--color-text-muted)' }}>LLM Calls</div>
          <div className="font-medium" style={{ color: 'var(--color-text-main)' }}>{llmCalls.toLocaleString()}</div>
        </div>
        <div className="p-2 rounded" style={{ background: 'var(--color-background)' }}>
          <div style={{ color: 'var(--color-text-muted)' }}>Avg Latency</div>
          <div className="font-medium" style={{ color: 'var(--color-text-main)' }}>{avgQueryLatency} ms</div>
        </div>
      </div>

      {/* Storage bars per namespace */}
      {namespaceStorages.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Storage per Namespace
          </div>
          {namespaceStorages.map(ns => (
            <StorageBar 
              key={ns.name} 
              bytes={ns.bytes} 
              maxBytes={maxStorage} 
              label={ns.name} 
            />
          ))}
        </div>
      )}

      {/* Timestamp */}
      <div className="text-xs text-right" style={{ color: 'var(--color-text-muted)' }}>
        Updated: {new Date(metrics.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}
