'use client';

import React, { useEffect, useState, useCallback } from 'react';

// ── Types ────────────────────────────────────────────────────────────

interface CostEntry {
  name?: string;
  model?: string;
  provider?: string;
  agent?: string;
  date?: string;
  cost: number;
  calls: number;
  tokens?: number;
}

interface AgentCosts {
  total_cost: number;
  total_messages: number;
  date_range: { from: string | null; to: string | null };
  by_project: CostEntry[];
  by_model: CostEntry[];
  by_agent: CostEntry[];
  by_day: CostEntry[];
  error?: string;
}

interface GatewayStats {
  total_completions: number;
  total_embeddings: number;
  total_errors: number;
  completions_by_model: Record<string, number>;
  embeddings_by_model: Record<string, number>;
  completions_by_purpose: Record<string, number>;
  avg_completion_latency_ms: number;
  avg_embedding_latency_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  recent_calls: Array<{
    type: string;
    model: string;
    purpose?: string;
    latency_ms: number;
    success: boolean;
    timestamp: string;
    caller?: string;
  }>;
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatCost(cost: number): string {
  if (cost >= 1000) return `$${(cost / 1000).toFixed(1)}k`;
  if (cost >= 1) return `$${cost.toFixed(2)}`;
  if (cost >= 0.01) return `$${cost.toFixed(3)}`;
  return `$${cost.toFixed(4)}`;
}

function CostBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden flex-1">
      <div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

function CostTable({
  title, icon, items, labelKey, maxCost,
}: {
  title: string; icon: string; items: CostEntry[]; labelKey: 'name' | 'model' | 'agent'; maxCost: number;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        <span className="material-symbols-outlined text-sm text-slate-400">{icon}</span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{title}</span>
      </div>
      <div className="space-y-1.5">
        {items.slice(0, 8).map((item, i) => {
          const label = item[labelKey] || 'unknown';
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[11px] text-slate-700 truncate w-28" title={label}>{label}</span>
              <CostBar value={item.cost} max={maxCost} />
              <span className="text-[10px] font-mono text-slate-500 w-16 text-right">{formatCost(item.cost)}</span>
              <span className="text-[9px] text-slate-400 w-12 text-right">{item.calls}</span>
            </div>
          );
        })}
        {items.length === 0 && <p className="text-[10px] text-slate-400">No data</p>}
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────

export function AgentCostsPanel() {
  const [costs, setCosts] = useState<AgentCosts | null>(null);
  const [gateway, setGateway] = useState<GatewayStats | null>(null);
  const [days, setDays] = useState(30);
  const [includePersonal, setIncludePersonal] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [costsRes, gwRes] = await Promise.allSettled([
        fetch(`/api/ai/agent-costs?days=${days}&include_personal=${includePersonal}`),
        fetch('/api/ai/stats'),
      ]);
      if (costsRes.status === 'fulfilled' && costsRes.value.ok) setCosts(await costsRes.value.json());
      if (gwRes.status === 'fulfilled' && gwRes.value.ok) setGateway(await gwRes.value.json());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [days, includePersonal]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  if (loading && !costs && !gateway) {
    return (
      <div className="animate-pulse space-y-3 p-4">
        <div className="h-6 w-40 bg-slate-100 rounded" />
        <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-20 bg-slate-50 rounded-lg" />)}</div>
      </div>
    );
  }

  const maxProjectCost = Math.max(...(costs?.by_project || []).map(p => p.cost), 0.01);
  const maxModelCost = Math.max(...(costs?.by_model || []).map(m => m.cost), 0.01);
  const maxAgentCost = Math.max(...(costs?.by_agent || []).map(a => a.cost), 0.01);
  const dailyCosts = (costs?.by_day || []).slice(-30);
  const maxDailyCost = Math.max(...dailyCosts.map(d => d.cost), 0.01);

  const gwTotal = gateway ? gateway.total_completions + gateway.total_embeddings : 0;

  return (
    <div className="space-y-8">

      {/* ── Section 1: Agent Costs ────────────────────────────────── */}
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-lg text-amber-600">payments</span>
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Agent Costs</h3>

          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-[10px] text-slate-500 cursor-pointer">
              <input type="checkbox" checked={includePersonal} onChange={e => setIncludePersonal(e.target.checked)} className="rounded border-slate-300" />
              Include personal
            </label>
            <select value={days} onChange={e => setDays(parseInt(e.target.value, 10))} className="text-[10px] px-2 py-1 rounded border border-slate-200 bg-white text-slate-600">
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
              <option value={365}>1 year</option>
            </select>
          </div>
        </div>

        {costs && !costs.error ? (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-4 gap-3">
              <div className="rounded-lg border border-slate-200 p-3">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider">Total Cost</span>
                <p className="text-xl font-bold text-slate-800 mt-0.5">{formatCost(costs.total_cost)}</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider">Messages</span>
                <p className="text-xl font-bold text-slate-800 mt-0.5">{costs.total_messages.toLocaleString()}</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider">Projects</span>
                <p className="text-xl font-bold text-slate-800 mt-0.5">{costs.by_project.length}</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider">Date Range</span>
                <p className="text-xs font-medium text-slate-600 mt-1">{costs.date_range.from || '—'} to {costs.date_range.to || '—'}</p>
              </div>
            </div>

            {/* Daily sparkline */}
            {dailyCosts.length > 1 && (
              <div className="rounded-lg border border-slate-200 p-3">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider">Daily Spend</span>
                <div className="flex items-end gap-[2px] mt-2 h-10">
                  {dailyCosts.map((d, i) => (
                    <div key={i} className="bg-blue-400 rounded-t-sm flex-1 min-w-[3px] transition-all hover:bg-blue-600"
                      style={{ height: `${Math.max(2, (d.cost / maxDailyCost) * 40)}px` }}
                      title={`${d.date}: ${formatCost(d.cost)} (${d.calls} calls)`} />
                  ))}
                </div>
              </div>
            )}

            {/* Breakdown tables */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <CostTable title="By Project" icon="folder" items={costs.by_project} labelKey="name" maxCost={maxProjectCost} />
              <CostTable title="By Model" icon="smart_toy" items={costs.by_model} labelKey="model" maxCost={maxModelCost} />
              <CostTable title="By Agent" icon="person" items={costs.by_agent} labelKey="agent" maxCost={maxAgentCost} />
            </div>
          </>
        ) : (
          <div className="rounded-lg p-4 border border-slate-200 bg-slate-50">
            <div className="flex items-center gap-2 text-slate-400 text-xs">
              <span className="material-symbols-outlined text-sm">info</span>
              {costs?.error || 'Agent cost data not available'}
            </div>
          </div>
        )}
      </div>

      {/* ── Section 2: Gateway Activity ──────────────────────────── */}
      {gateway && (
        <div className="space-y-4 border-t border-slate-200 pt-6">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-lg text-blue-600">hub</span>
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-700">Gateway Activity</h3>
            <span className="text-[9px] text-slate-400">(memory + knowledge)</span>
          </div>

          {/* Gateway summary */}
          <div className="grid grid-cols-5 gap-3">
            <div className="rounded-lg border border-slate-200 p-3">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Total Calls</span>
              <p className="text-xl font-bold text-slate-800 mt-0.5">{gwTotal}</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Completions</span>
              <p className="text-xl font-bold text-slate-800 mt-0.5">{gateway.total_completions}</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Embeddings</span>
              <p className="text-xl font-bold text-slate-800 mt-0.5">{gateway.total_embeddings}</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Avg Latency</span>
              <p className="text-sm font-bold text-slate-800 mt-0.5">
                {gateway.avg_completion_latency_ms > 0 ? `${Math.round(gateway.avg_completion_latency_ms)}ms` : '—'}
              </p>
              <p className="text-[9px] text-slate-400">completions</p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <span className="text-[9px] text-slate-400 uppercase tracking-wider">Errors</span>
              <p className={`text-xl font-bold mt-0.5 ${gateway.total_errors > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {gateway.total_errors}
              </p>
            </div>
          </div>

          {/* Gateway model breakdown */}
          {(Object.keys(gateway.completions_by_model).length > 0 || Object.keys(gateway.embeddings_by_model).length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {Object.keys(gateway.completions_by_model).length > 0 && (
                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Completions by Model</span>
                  {Object.entries(gateway.completions_by_model).sort((a, b) => b[1] - a[1]).map(([model, count]) => (
                    <div key={model} className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-700 truncate w-40">{model}</span>
                      <CostBar value={count} max={Math.max(...Object.values(gateway.completions_by_model))} />
                      <span className="text-[10px] font-mono text-slate-500 w-10 text-right">{count}</span>
                    </div>
                  ))}
                </div>
              )}
              {Object.keys(gateway.embeddings_by_model).length > 0 && (
                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Embeddings by Model</span>
                  {Object.entries(gateway.embeddings_by_model).sort((a, b) => b[1] - a[1]).map(([model, count]) => (
                    <div key={model} className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-700 truncate w-40">{model}</span>
                      <CostBar value={count} max={Math.max(...Object.values(gateway.embeddings_by_model))} />
                      <span className="text-[10px] font-mono text-slate-500 w-10 text-right">{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Recent calls table */}
          {gateway.recent_calls.length > 0 && (
            <div className="space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Recent Calls</span>
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <th className="text-left px-3 py-1.5 text-[9px] uppercase text-slate-400 font-medium">Type</th>
                      <th className="text-left px-3 py-1.5 text-[9px] uppercase text-slate-400 font-medium">Model</th>
                      <th className="text-left px-3 py-1.5 text-[9px] uppercase text-slate-400 font-medium">Purpose</th>
                      <th className="text-right px-3 py-1.5 text-[9px] uppercase text-slate-400 font-medium">Latency</th>
                      <th className="text-center px-3 py-1.5 text-[9px] uppercase text-slate-400 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gateway.recent_calls.slice(0, 15).map((call, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-1.5">{call.type}</td>
                        <td className="px-3 py-1.5 font-mono text-slate-600 truncate max-w-[180px]" title={call.model}>
                          {call.model.split('/').pop()}
                        </td>
                        <td className="px-3 py-1.5 text-slate-500">{call.purpose || '—'}</td>
                        <td className="px-3 py-1.5 text-right font-mono">{call.latency_ms.toFixed(0)}ms</td>
                        <td className="px-3 py-1.5 text-center">
                          <span className={`inline-block w-2 h-2 rounded-full ${call.success ? 'bg-green-400' : 'bg-red-400'}`} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
