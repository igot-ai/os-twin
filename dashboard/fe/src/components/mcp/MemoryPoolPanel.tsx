'use client';

import React, { useEffect, useState, useCallback } from 'react';

// ── Types ────────────────────────────────────────────────────────────

interface SlotInfo {
  persist_dir: string;
  notes_count: number;
  idle_seconds: number;
  created_ago_s: number;
  sync_thread_alive: boolean;
}

interface PoolConfig {
  idle_timeout_s: number;
  max_instances: number;
  eviction_policy: string;
  sync_interval_s: number;
}

interface PoolHealth {
  ml_ready: boolean;
  active_slots: number;
  slots: SlotInfo[];
  config: PoolConfig;
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function idlePercent(idle: number, timeout: number): number {
  if (timeout <= 0) return 0;
  return Math.min(100, (idle / timeout) * 100);
}

function shortDir(dir: string): string {
  // Show last 2 path segments for readability
  const parts = dir.replace(/\/$/, '').split('/');
  return parts.slice(-2).join('/');
}

// ── Component ────────────────────────────────────────────────────────

export default function MemoryPoolPanel() {
  const [health, setHealth] = useState<PoolHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/api/knowledge/health');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PoolHealth = await res.json();
      setHealth(data);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to fetch pool health');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000); // poll every 5s
    return () => clearInterval(interval);
  }, [fetchHealth]);

  if (loading && !health) {
    return (
      <div className="p-8 animate-pulse flex flex-col gap-4">
        <div className="h-8 w-48 bg-border/20 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-border/10 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className="p-8">
        <div className="rounded-xl p-6 border border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-2 text-red-400 mb-2">
            <span className="material-symbols-outlined text-xl">error</span>
            <span className="font-semibold">Dashboard Not Reachable</span>
          </div>
          <p className="text-sm text-text-secondary">
            {error}. Make sure the dashboard is running on port 3366.
          </p>
        </div>
      </div>
    );
  }

  if (!health) return null;

  const { ml_ready, active_slots, slots, config } = health;

  return (
    <div className="p-6 h-full overflow-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-text-main">Memory Pool</h2>
          <p className="text-sm text-text-secondary mt-0.5">
            HTTP MCP at <code className="text-xs bg-border/20 px-1.5 py-0.5 rounded">/api/knowledge/mcp</code>
          </p>
        </div>
        <button
          onClick={fetchHealth}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-text-secondary hover:text-text-main hover:bg-border/20 transition-colors"
        >
          <span className="material-symbols-outlined text-base">refresh</span>
          Refresh
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-4 gap-4">
        {/* ML Ready */}
        <div className="rounded-xl border border-border p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary uppercase tracking-wider">ML Runtime</span>
            <span className={`inline-block w-2 h-2 rounded-full ${ml_ready ? 'bg-green-400' : 'bg-yellow-400 animate-pulse'}`} />
          </div>
          <p className="text-xl font-bold text-text-main">{ml_ready ? 'Ready' : 'Loading'}</p>
          <p className="text-xs text-text-secondary">
            {ml_ready ? 'torch + embeddings loaded' : 'Preloading ML libraries...'}
          </p>
        </div>

        {/* Active Slots */}
        <div className="rounded-xl border border-border p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary uppercase tracking-wider">Active Slots</span>
            <span className="material-symbols-outlined text-base text-text-secondary">memory</span>
          </div>
          <p className="text-xl font-bold text-text-main">
            {active_slots} <span className="text-sm font-normal text-text-secondary">/ {config.max_instances}</span>
          </p>
          <p className="text-xs text-text-secondary">
            {config.eviction_policy} eviction
          </p>
        </div>

        {/* Idle Timeout */}
        <div className="rounded-xl border border-border p-4 space-y-1">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Idle Timeout</span>
          <p className="text-xl font-bold text-text-main">{formatSeconds(config.idle_timeout_s)}</p>
          <p className="text-xs text-text-secondary">
            sync every {formatSeconds(config.sync_interval_s)}
          </p>
        </div>

        {/* Total Notes */}
        <div className="rounded-xl border border-border p-4 space-y-1">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Total Notes</span>
          <p className="text-xl font-bold text-text-main">
            {slots.reduce((sum, s) => sum + s.notes_count, 0)}
          </p>
          <p className="text-xs text-text-secondary">
            across {active_slots} slot{active_slots !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      {/* Slots Table */}
      {slots.length > 0 ? (
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-border/5">
                <th className="text-left px-4 py-3 text-xs text-text-secondary uppercase tracking-wider font-medium">persist_dir</th>
                <th className="text-center px-4 py-3 text-xs text-text-secondary uppercase tracking-wider font-medium">Notes</th>
                <th className="text-center px-4 py-3 text-xs text-text-secondary uppercase tracking-wider font-medium">Age</th>
                <th className="text-left px-4 py-3 text-xs text-text-secondary uppercase tracking-wider font-medium">Idle</th>
                <th className="text-center px-4 py-3 text-xs text-text-secondary uppercase tracking-wider font-medium">Sync</th>
              </tr>
            </thead>
            <tbody>
              {slots.map((slot) => {
                const pct = idlePercent(slot.idle_seconds, config.idle_timeout_s);
                const isHot = pct < 20;
                const isWarm = pct >= 20 && pct < 70;
                const isDanger = pct >= 70;

                return (
                  <tr key={slot.persist_dir} className="border-b border-border/50 hover:bg-border/5 transition-colors">
                    {/* Path */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`material-symbols-outlined text-base ${isHot ? 'text-green-400' : isWarm ? 'text-yellow-400' : 'text-red-400'}`}>
                          {isHot ? 'bolt' : isWarm ? 'schedule' : 'hourglass_bottom'}
                        </span>
                        <div>
                          <p className="text-text-main font-medium">{shortDir(slot.persist_dir)}</p>
                          <p className="text-xs text-text-secondary truncate max-w-md" title={slot.persist_dir}>{slot.persist_dir}</p>
                        </div>
                      </div>
                    </td>

                    {/* Notes count */}
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                        {slot.notes_count}
                      </span>
                    </td>

                    {/* Age */}
                    <td className="px-4 py-3 text-center text-text-secondary text-xs">
                      {formatSeconds(slot.created_ago_s)}
                    </td>

                    {/* Idle progress */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-border/20 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              isHot ? 'bg-green-400' : isWarm ? 'bg-yellow-400' : 'bg-red-400'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs text-text-secondary w-12 text-right">
                          {formatSeconds(slot.idle_seconds)}
                        </span>
                      </div>
                    </td>

                    {/* Sync thread */}
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block w-2 h-2 rounded-full ${slot.sync_thread_alive ? 'bg-green-400' : 'bg-red-400'}`} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-border/50 p-8 text-center">
          <span className="material-symbols-outlined text-4xl text-text-secondary/30 mb-3 block">inbox</span>
          <p className="text-text-secondary text-sm">No active memory slots</p>
          <p className="text-text-secondary/60 text-xs mt-1">
            Slots are created when agents connect via <code className="bg-border/20 px-1 rounded">?persist_dir=</code>
          </p>
        </div>
      )}

      {/* Error banner (if polling fails but we had data before) */}
      {error && health && (
        <div className="rounded-lg px-4 py-2 bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">warning</span>
          Poll failed: {error} — showing stale data
        </div>
      )}
    </div>
  );
}
