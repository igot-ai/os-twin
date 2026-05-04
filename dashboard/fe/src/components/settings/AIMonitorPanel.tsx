'use client';

import { useAIStats, type AIRecentCall } from '@/hooks/use-ai-stats';
import { apiPost } from '@/lib/api-client';

function formatTimestamp(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function StatCard({
  label,
  value,
  subtitle,
  icon,
  color = '#2563eb',
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <div className="flex items-center gap-3 mb-2">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${color}15` }}
        >
          <span className="material-symbols-outlined text-lg" style={{ color }}>
            {icon}
          </span>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold text-text-main">{value}</p>
      {subtitle && (
        <p className="text-[11px] text-text-secondary mt-1">{subtitle}</p>
      )}
    </div>
  );
}

function BreakdownTable({
  title,
  data,
  icon,
}: {
  title: string;
  data: Record<string, number>;
  icon: string;
}) {
  const sorted = Object.entries(data).sort(([, a], [, b]) => b - a);
  if (sorted.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">{icon}</span>
          {title}
        </h3>
        <p className="text-xs text-text-secondary">No data yet</p>
      </div>
    );
  }
  const max = sorted[0][1];
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-sm">{icon}</span>
        {title}
      </h3>
      <div className="space-y-2">
        {sorted.map(([key, count]) => (
          <div key={key}>
            <div className="flex justify-between text-[11px] mb-1">
              <span className="text-text-main font-mono truncate max-w-[200px]" title={key}>
                {key}
              </span>
              <span className="text-text-secondary font-semibold">{count}</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-500"
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentCallsTable({ calls }: { calls: AIRecentCall[] }) {
  if (calls.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">history</span>
          Recent Calls
        </h3>
        <p className="text-xs text-text-secondary">No calls recorded yet. AI gateway calls will appear here.</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3 flex items-center gap-2">
        <span className="material-symbols-outlined text-sm">history</span>
        Recent Calls ({calls.length})
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 px-2 text-text-secondary font-semibold">Time</th>
              <th className="text-left py-2 px-2 text-text-secondary font-semibold">Type</th>
              <th className="text-left py-2 px-2 text-text-secondary font-semibold">Model</th>
              <th className="text-left py-2 px-2 text-text-secondary font-semibold">Purpose</th>
              <th className="text-left py-2 px-2 text-text-secondary font-semibold">Caller</th>
              <th className="text-right py-2 px-2 text-text-secondary font-semibold">Latency</th>
              <th className="text-center py-2 px-2 text-text-secondary font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {[...calls].reverse().map((call, i) => (
              <tr key={i} className="border-b border-border/50 hover:bg-slate-50 transition-colors">
                <td className="py-1.5 px-2 font-mono text-text-secondary">
                  {formatTimestamp(call.timestamp)}
                </td>
                <td className="py-1.5 px-2">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      call.type === 'completion'
                        ? 'bg-blue-50 text-blue-700'
                        : 'bg-purple-50 text-purple-700'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[12px]">
                      {call.type === 'completion' ? 'chat' : 'conversion_path'}
                    </span>
                    {call.type}
                  </span>
                </td>
                <td className="py-1.5 px-2 font-mono text-text-main truncate max-w-[180px]" title={call.model}>
                  {call.model.split('/').pop()}
                </td>
                <td className="py-1.5 px-2 text-text-secondary">
                  {call.purpose || '-'}
                </td>
                <td className="py-1.5 px-2 font-mono text-text-secondary truncate max-w-[150px]" title={call.caller || ''}>
                  {call.caller || '-'}
                </td>
                <td className="py-1.5 px-2 text-right font-mono text-text-main">
                  {call.latency_ms.toFixed(0)}ms
                </td>
                <td className="py-1.5 px-2 text-center">
                  {call.success ? (
                    <span className="text-green-600 material-symbols-outlined text-[14px]">check_circle</span>
                  ) : (
                    <span className="text-red-500 material-symbols-outlined text-[14px]">error</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AIMonitorPanel() {
  const { stats, isLoading, isError, refresh } = useAIStats(5000);

  const handleReset = async () => {
    try {
      await apiPost('/ai/stats/reset', {});
      refresh();
    } catch {
      // ignore
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-slate-100 rounded w-48" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-100 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6 text-center">
        <span className="material-symbols-outlined text-4xl text-text-secondary mb-2">cloud_off</span>
        <p className="text-sm text-text-secondary">Failed to load AI gateway stats</p>
      </div>
    );
  }

  const totalCalls = stats.total_completions + stats.total_embeddings;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-text-main flex items-center gap-2">
            <span className="material-symbols-outlined text-blue-600">monitoring</span>
            AI Gateway Monitor
          </h2>
          <p className="text-xs text-text-secondary mt-1">
            All LLM and embedding calls route through shared/ai. Stats auto-refresh every 5s.
          </p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-text-secondary hover:bg-slate-100 border border-border transition-colors"
        >
          <span className="material-symbols-outlined text-sm">restart_alt</span>
          Reset
        </button>
      </div>

      {/* Top-line stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Calls"
          value={totalCalls}
          subtitle={`${stats.total_completions} completions + ${stats.total_embeddings} embeddings`}
          icon="swap_vert"
          color="#2563eb"
        />
        <StatCard
          label="Errors"
          value={stats.total_errors}
          subtitle={totalCalls > 0 ? `${((stats.total_errors / totalCalls) * 100).toFixed(1)}% error rate` : 'No calls yet'}
          icon="error_outline"
          color={stats.total_errors > 0 ? '#dc2626' : '#16a34a'}
        />
        <StatCard
          label="Avg Completion"
          value={`${stats.avg_completion_latency_ms.toFixed(0)}ms`}
          subtitle={`${stats.total_input_tokens.toLocaleString()} in / ${stats.total_output_tokens.toLocaleString()} out tokens`}
          icon="speed"
          color="#7c3aed"
        />
        <StatCard
          label="Avg Embedding"
          value={`${stats.avg_embedding_latency_ms.toFixed(0)}ms`}
          subtitle={`${stats.total_embeddings} calls`}
          icon="conversion_path"
          color="#0891b2"
        />
      </div>

      {/* Breakdowns */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <BreakdownTable
          title="By Model"
          data={{ ...stats.completions_by_model, ...stats.embeddings_by_model }}
          icon="smart_toy"
        />
        <BreakdownTable
          title="By Purpose"
          data={stats.completions_by_purpose}
          icon="category"
        />
        <BreakdownTable
          title="By Caller"
          data={stats.calls_by_caller}
          icon="code"
        />
      </div>

      {/* Recent calls log */}
      <RecentCallsTable calls={stats.recent_calls} />
    </div>
  );
}
