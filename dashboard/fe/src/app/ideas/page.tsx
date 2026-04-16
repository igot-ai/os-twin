'use client';


import Link from 'next/link';
import { usePlanningThreads } from '@/hooks/use-planning-threads';
import { Skeleton } from '@/components/ui/Skeleton';

export default function IdeasIndexPage() {
  const { threads, isLoading, error } = usePlanningThreads();

  if (isLoading) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-6" style={{ color: 'var(--color-text-main)' }}>Your Ideas</h1>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500">Error loading ideas</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text-main)' }}>Ideas</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>Explore and develop your initial thoughts into full plans.</p>
        </div>
        <Link 
          href="/"
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium hover:opacity-90 transition-opacity shadow-sm"
          style={{ background: 'var(--color-primary)' }}
        >
          <span className="material-symbols-outlined text-sm">add</span>
          New Idea
        </Link>
      </div>

      {threads.length === 0 ? (
        <div 
          className="flex flex-col items-center justify-center py-20 border-2 border-dashed rounded-2xl"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
        >
          <div 
            className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
            style={{ background: 'var(--color-surface-alt)' }}
          >
            <span className="material-symbols-outlined text-3xl" style={{ color: 'var(--color-text-muted)' }}>lightbulb</span>
          </div>
          <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--color-text-main)' }}>No ideas yet</h3>
          <p className="text-sm mb-6" style={{ color: 'var(--color-text-faint)' }}>Start your first idea from the home page.</p>
          <Link 
            href="/"
            className="text-sm font-bold hover:underline"
            style={{ color: 'var(--color-primary)' }}
          >
            Go to Home
          </Link>
        </div>
      ) : (
        <div className="grid gap-3">
          {threads.map((thread) => (
            <Link
              key={thread.id}
              href={`/ideas/${thread.id}`}
              className="flex items-center justify-between p-4 rounded-xl border transition-all group"
              style={{ 
                borderColor: 'var(--color-border)', 
                background: 'var(--color-surface)' 
              }}
            >
              <div className="flex items-center gap-4 min-w-0">
                <div 
                  className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: 'var(--color-surface-alt)', color: 'var(--color-primary)' }}
                >
                  <span className="material-symbols-outlined text-xl">lightbulb</span>
                </div>
                <div className="min-w-0">
                  <h3 
                    className="font-bold truncate pr-4 transition-colors"
                    style={{ color: 'var(--color-text-main)' }}
                  >
                    {thread.title || 'New Idea'}
                  </h3>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-faint)' }}>
                    Updated {new Date(thread.updated_at || Date.now()).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {thread.status === 'promoted' && (
                  <span 
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider"
                    style={{ background: 'rgba(34, 197, 94, 0.1)', color: 'rgb(34, 197, 94)' }}
                  >
                    <span className="material-symbols-outlined text-[14px]">check_circle</span>
                    Promoted
                  </span>
                )}
                <span 
                  className="material-symbols-outlined text-[20px] transition-colors"
                  style={{ color: 'var(--color-text-faint)' }}
                >
                  chevron_right
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
