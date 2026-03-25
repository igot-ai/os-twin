'use client';

import { Trend } from '@/types';
import { ReactNode, useEffect, useState } from 'react';
import { Skeleton } from '../ui/Skeleton';

interface MetricCardProps {
  label: string;
  value: number;
  trend: Trend;
  color: string;
  icon: string;
  visualization?: ReactNode;
  suffix?: string;
  isLoading?: boolean;
}

export default function MetricCard({ 
  label, 
  value, 
  trend, 
  color, 
  icon, 
  visualization, 
  suffix = '',
  isLoading = false
}: MetricCardProps) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (isLoading) return;
    
    let animationFrameId: number;
    const start = displayValue;
    const end = value;
    if (start === end) return;

    const duration = 1000;
    const startTime = performance.now();
    
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const easedProgress = progress * (2 - progress);
      const currentVal = Math.floor(start + (end - start) * easedProgress);
      
      setDisplayValue(currentVal);
      
      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate);
      }
    };
    
    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, isLoading]);

  if (isLoading) {
    return <MetricCardSkeleton />;
  }

  const trendColor = trend.direction === 'up'
    ? 'var(--color-success)'
    : trend.direction === 'down'
    ? 'var(--color-danger)'
    : 'var(--color-text-faint)';

  const trendIcon = trend.direction === 'up' ? 'trending_up' : trend.direction === 'down' ? 'trending_down' : 'trending_flat';

  return (
    <div
      className="flex-1 min-w-[200px] p-5 rounded-xl border transition-all duration-200 group bg-surface border-border shadow-card hover:shadow-card-hover hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: `${color}14`, color }}
        >
          <span className="material-symbols-outlined text-lg">{icon}</span>
        </div>
        {visualization}
      </div>

      <div className="text-2xl font-extrabold tracking-tight mb-1 text-text-main">
        {displayValue}{suffix}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-muted">{label}</span>
        <div className="flex items-center gap-1">
          <span className="material-symbols-outlined text-sm" style={{ color: trendColor, fontSize: 14 }}>
            {trendIcon}
          </span>
          <span className="text-[11px] font-semibold" style={{ color: trendColor }}>
            {trend.direction === 'up' ? '+' : trend.direction === 'down' ? '-' : ''}{trend.delta}
          </span>
        </div>
      </div>
    </div>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="flex-1 min-w-[200px] p-5 rounded-xl border border-border bg-surface shadow-card">
      <div className="flex items-start justify-between mb-3">
        <Skeleton className="w-9 h-9 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-24 mb-2" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  );
}

