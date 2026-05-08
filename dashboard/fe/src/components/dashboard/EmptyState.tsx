'use client';


import { Button } from '../ui/Button';

interface EmptyStateProps {
  onClear: () => void;
  message?: string;
  icon?: string;
}

export default function EmptyState({ 
  onClear, 
  message = "No plans match your filters", 
  icon = "search_off" 
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 rounded-2xl border-2 border-dashed border-border bg-surface-hover/30">
      <div className="w-16 h-16 rounded-full flex items-center justify-center bg-surface border border-border shadow-sm mb-4">
        <span className="material-symbols-outlined text-4xl text-text-faint">{icon}</span>
      </div>
      <h3 className="text-lg font-bold text-text-main mb-1">{message}</h3>
      <p className="text-sm text-text-muted mb-6 text-center max-w-sm">
        Try adjusting your search or filters to find what you&apos;re looking for.
      </p>
      <Button 
        variant="outline" 
        onClick={onClear}
        className="flex items-center gap-2"
      >
        <span className="material-symbols-outlined text-lg">filter_alt_off</span>
        Clear All Filters
      </Button>
    </div>
  );
}
