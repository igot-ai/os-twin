'use client';


import { Epic } from '@/types';

interface TokenBudgetChartProps {
  epic: Epic;
}

export default function TokenBudgetChart({ epic }: TokenBudgetChartProps) {
  const { epic_ref, budget_tokens = { used: 0, max: 100 } } = epic;
  const { used, max } = budget_tokens;
  const utilization = (used / max) * 100;

  // Determine color based on utilization
  let colorClass = 'bg-success';
  if (utilization > 90) {
    colorClass = 'bg-danger';
  } else if (utilization > 70) {
    colorClass = 'bg-warning';
  }

  // Helper to format large numbers (e.g., 1.2M)
  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  return (
    <div className="group space-y-2 py-2 border-b border-border last:border-0 hover:bg-surface-hover/50 px-2 transition-colors rounded-md">
      <div className="flex items-center justify-between text-xs font-medium">
        <span className="text-text-main font-mono">{epic_ref}</span>
        <span className="text-text-muted">
          {formatNumber(used)} / {formatNumber(max)}
        </span>
      </div>
      
      <div className="h-2 w-full bg-border rounded-full overflow-hidden">
        <div 
          className={`h-full ${colorClass} transition-all duration-500 ease-out rounded-full`}
          style={{ width: `${Math.min(utilization, 100)}%` }}
        />
      </div>
      
      {utilization > 100 && (
        <div className="text-[10px] text-danger font-semibold mt-1 flex items-center gap-1">
          <span className="material-symbols-outlined text-[12px]">warning</span>
          Budget exceeded by {Math.round(utilization - 100)}%
        </div>
      )}
    </div>
  );
}
