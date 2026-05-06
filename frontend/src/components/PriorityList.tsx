import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { deleteUserTask, dismissEmail, type PriorityItem } from '../lib/api/client';
import { PriorityCard } from './PriorityCard';
import { ActiveCard } from './ActiveCard';

interface PriorityListProps {
  priorities: PriorityItem[];
  openPriorityId?: string | null;
  closeAllCounter?: number;
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-4xl mb-4" role="img" aria-label="celebration">
        🎉
      </span>
      <p className="text-stone-300 font-semibold">All caught up!</p>
      <p className="text-stone-600 text-sm mt-1">
        No priorities at the moment. Marimba is proud of you.
      </p>
    </div>
  );
}

export function PriorityList({ priorities, openPriorityId, closeAllCounter = 0 }: PriorityListProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  useEffect(() => {
    if (openPriorityId !== undefined) {
      setActiveId(openPriorityId);
    }
  }, [openPriorityId]);

  useEffect(() => {
    if (closeAllCounter > 0) setActiveId(null);
  }, [closeAllCounter]);

  const remaining = priorities.filter((p) => !doneIds.has(p.id));
  const active = remaining.find((p) => p.id === activeId);

  const handleDone = async (item: PriorityItem) => {
    // Optimistically hide the card immediately
    setDoneIds((prev) => new Set([...prev, item.id]));
    setActiveId(null);

    // Persist to server based on source — meetings/action_items have no server delete
    try {
      if (item.source === 'user_task') {
        // IDs are prefixed "user_<uuid>" — strip the prefix for the API call
        const rawId = item.id.replace(/^user_/, '');
        await deleteUserTask(rawId);
        queryClient.invalidateQueries({ queryKey: ['tasks'] });
      } else if (item.source === 'email') {
        await dismissEmail(item.id);
        queryClient.invalidateQueries({ queryKey: ['important-emails'] });
      }
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    } catch (err) {
      console.error('[PriorityList] Failed to delete priority item:', err);
      // Don't undo the optimistic hide — a failed delete is better than a stale card reappearing
    }
  };

  // Active card view — one task takes full focus
  if (active) {
    const rank = remaining.findIndex((p) => p.id === activeId) + 1;
    return (
      <section aria-label="Active task">
        <ActiveCard
          priority={active}
          rank={rank}
          onBack={() => setActiveId(null)}
          onDone={() => handleDone(active)}
        />
      </section>
    );
  }

  // Grid view — all remaining tasks
  return (
    <section aria-label="Your top priorities">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          Top {remaining.length} · Right Now
        </h2>
      </div>

      {remaining.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {remaining.map((priority, index) => (
            <PriorityCard
              key={priority.id}
              priority={priority}
              rank={index + 1}
              onStart={() => setActiveId(priority.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
