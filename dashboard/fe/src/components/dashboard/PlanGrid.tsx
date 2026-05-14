'use client';

import { useState, useMemo, useEffect } from 'react';
import { usePlans } from '@/hooks/use-plans';
import PlanCard, { PlanCardSkeleton } from './PlanCard';
import FilterBar, { SortOption } from './FilterBar';
import EmptyState from './EmptyState';
import { PlanStatus, Domain } from '@/types';
import { useRouter } from 'next/navigation';

export default function PlanGrid() {
  const [view, setView] = useState<'grid' | 'table'>('grid');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statuses, setStatuses] = useState<PlanStatus[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [sort, setSort] = useState<SortOption>('newest');
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const router = useRouter();

  // Debounce search input before sending to server (300ms)
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(handler);
  }, [search]);

  // Server-side zvec vector search via ?q= parameter
  const { plans, isLoading, isError, deletePlan } = usePlans(debouncedSearch);

  const filteredPlans = useMemo(() => {
    if (!plans) return [];

    let result = [...plans];

    // Search is handled server-side via zvec — no client-side text filter needed

    // Status (cheap client-side filter)
    if (statuses.length > 0) {
      result = result.filter(p => p.status && statuses.includes(p.status));
    }

    // Domain (cheap client-side filter)
    if (domains.length > 0) {
      result = result.filter(p => p.domain && domains.includes(p.domain));
    }

    // When searching, preserve zvec relevance ranking (server already sorted).
    // Only apply client-side sort when there's no active search query.
    if (!debouncedSearch) {
      result.sort((a, b) => {
        switch (sort) {
          case 'newest':
            return new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime();
          case 'oldest':
            return new Date(a.created_at ?? 0).getTime() - new Date(b.created_at ?? 0).getTime();
          case 'progress-high':
            return (b.pct_complete ?? 0) - (a.pct_complete ?? 0);
          case 'progress-low':
            return (a.pct_complete ?? 0) - (b.pct_complete ?? 0);
          case 'alphabetical':
            return a.title.localeCompare(b.title);
          default:
            return 0;
        }
      });
    }

    return result;
  }, [plans, debouncedSearch, statuses, domains, sort]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (view !== 'grid') return;

      if (e.key === 'j') {
        setSelectedIndex(prev => Math.min(prev + 1, filteredPlans.length - 1));
      } else if (e.key === 'k') {
        setSelectedIndex(prev => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter' && selectedIndex >= 0) {
        router.push(`/plans/${filteredPlans[selectedIndex].plan_id}`);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [filteredPlans, selectedIndex, router, view]);

  const clearFilters = () => {
    setSearch('');
    setStatuses([]);
    setDomains([]);
  };

  if (isError) {
    return (
      <div className="py-20 text-center">
        <p className="text-danger font-medium">Failed to load plans. Please try again later.</p>
      </div>
    );
  }

  const availableDomains: Domain[] = ['software', 'data', 'audit', 'compliance', 'custom'];
  const availableStatuses: PlanStatus[] = ['active', 'draft', 'completed', 'archived'];

  return (
    <div className="space-y-6">
      <FilterBar 
        onSearchChange={setSearch}
        onStatusChange={setStatuses}
        onDomainChange={setDomains}
        onSortChange={setSort}
        onViewChange={setView}
        currentView={view}
        availableDomains={availableDomains}
        availableStatuses={availableStatuses}
      />

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
          {[...Array(6)].map((_, i) => (
            <PlanCardSkeleton key={i} />
          ))}
        </div>
      ) : filteredPlans.length > 0 ? (
        view === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
            {filteredPlans.map((plan, index) => (
              <PlanCard 
                key={plan.plan_id} 
                plan={plan} 
                isFocused={index === selectedIndex}
                onDelete={deletePlan}
              />
            ))}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-surface shadow-card">
             <table className="w-full text-left text-sm border-collapse">
                <thead className="bg-surface-hover/50 text-text-muted font-semibold border-b border-border">
                  <tr>
                    <th className="px-4 py-3">Plan</th>
                    <th className="px-4 py-3">Domain</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Progress</th>
                    <th className="px-4 py-3">EPICs</th>
                    <th className="px-4 py-3 text-right">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-light">
                  {filteredPlans.map(plan => (
                    <tr 
                      key={plan.plan_id} 
                      className="hover:bg-surface-hover/30 transition-colors cursor-pointer group"
                      onClick={() => router.push(`/plans/${plan.plan_id}`)}
                    >
                      <td className="px-4 py-4">
                        <div className="font-bold text-text-main group-hover:text-primary transition-colors">{plan.title}</div>
                        <div className="text-[10px] text-text-muted line-clamp-1">{plan.goal ?? ''}</div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="capitalize px-2 py-0.5 rounded-full bg-primary-muted text-primary text-[10px] font-bold">
                          {plan.domain ?? 'custom'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`capitalize text-[10px] font-bold ${
                          plan.status === 'active' ? 'text-success' : 
                          plan.status === 'completed' ? 'text-primary' : 
                          'text-text-muted'
                        }`}>
                          {plan.status ?? 'draft'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                           <div className="w-24 h-1.5 bg-border-light rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-primary rounded-full transition-all duration-1000" 
                                style={{ width: `${plan.pct_complete ?? 0}%` }}
                              />
                           </div>
                           <span className="text-[10px] font-bold w-8 text-right">{plan.pct_complete ?? 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 font-medium text-text-main text-[12px]">
                        {plan.completed_epics ?? 0} <span className="text-text-muted">/ {plan.epic_count ?? 0}</span>
                      </td>
                      <td className="px-4 py-4 text-right text-text-faint text-[10px]">
                        {new Date(plan.updated_at || plan.created_at || 0).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
             </table>
          </div>
        )
      ) : (
        <EmptyState onClear={clearFilters} />
      )}
    </div>
  );
}
