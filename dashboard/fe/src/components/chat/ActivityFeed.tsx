
import Link from 'next/link';
import { usePlanningThreads } from '@/hooks/use-planning-threads';
import { Skeleton } from '@/components/ui/Skeleton';

export function ActivityFeed() {
  const { threads, isLoading } = usePlanningThreads(10);

  return (
    <div className="flex flex-col h-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-3 border-b border-[var(--color-border)]">
        <h3 className="text-xs font-semibold text-[var(--color-text-main)] uppercase tracking-wider">Recent Ideas</h3>
        <Link href="/ideas" className="text-xs text-[var(--color-primary)] hover:underline">
          View all
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="p-2 rounded hover:bg-[var(--color-surface-hover)]">
              <Skeleton className="h-4 w-3/4 mb-1" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))
        ) : threads.length === 0 ? (
          <div className="text-center py-6 text-xs text-[var(--color-text-muted)]">
            No ideas yet. Start brainstorming above!
          </div>
        ) : (
          threads.map(thread => (
            <Link
              key={thread.id}
              href={`/ideas/${thread.id}`}
              className="block p-2 rounded hover:bg-[var(--color-surface-hover)] transition-colors"
            >
              <div className="flex items-start gap-2">
                <span className="material-symbols-outlined text-[16px] text-[var(--color-text-muted)] mt-0.5">
                  lightbulb
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[var(--color-text-main)] truncate font-medium">
                    {thread.title || 'Untitled Idea'}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] text-[var(--color-text-faint)]">
                      {new Date(thread.created_at).toLocaleDateString()}
                    </span>
                    {thread.message_count > 0 && (
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {thread.message_count} messages
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
