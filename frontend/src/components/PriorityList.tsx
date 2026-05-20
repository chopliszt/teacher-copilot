import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { deleteUserTask, dismissEmail, recordPriorityFeedback, type PriorityItem } from '../lib/api/client';
import { PriorityCard } from './PriorityCard';
import { ActiveCard } from './ActiveCard';
import { TaskChatDrawer } from './TaskChatDrawer';

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

function buildContextJson(item: PriorityItem): string {
  return JSON.stringify({
    id: item.id,
    title: item.title,
    source: item.source,
    priority: item.priority,
    estimated_time: item.estimated_time,
    due_date: item.due_date,
    class: item.class,
    subject: item.subject,
  });
}

export function PriorityList({ priorities, openPriorityId, closeAllCounter = 0 }: PriorityListProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const [chatTask, setChatTask] = useState<PriorityItem | null>(null);
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

  const dismiss = async (item: PriorityItem, rating: 'relevant' | 'noise' | 'skip') => {
    setDoneIds((prev) => new Set([...prev, item.id]));
    setActiveId(null);

    // Fire feedback silently — never block the UI on this
    recordPriorityFeedback({
      task_id: item.id,
      task_title: item.title,
      source: item.source ?? 'unknown',
      priority_level: item.priority,
      rating,
      context_json: buildContextJson(item),
    }).catch(() => {/* silent — training data, not critical */});

    // Only "relevant" actually deletes the underlying record. 'noise' and
    // 'skip' just hide it locally — the backend re-derives suppression from
    // priority_feedback at the next /api/priorities call.
    try {
      if (rating === 'relevant') {
        if (item.source === 'user_task') {
          await deleteUserTask(item.id.replace(/^user_/, ''));
          queryClient.invalidateQueries({ queryKey: ['tasks'] });
        } else if (item.source === 'email') {
          await dismissEmail(item.id);
          queryClient.invalidateQueries({ queryKey: ['important-emails'] });
        }
      }
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    } catch (err) {
      console.error('[PriorityList] Failed to persist dismissal:', err);
    }
  };

  // Active card view — one task takes full focus
  if (active) {
    const rank = remaining.findIndex((p) => p.id === activeId) + 1;
    return (
      <>
        <section aria-label="Active task">
          <ActiveCard
            priority={active}
            rank={rank}
            onBack={() => setActiveId(null)}
            onDone={() => dismiss(active, 'relevant')}
            onNotRelevant={() => dismiss(active, 'noise')}
            onSkip={() => dismiss(active, 'skip')}
            onChat={() => setChatTask(active)}
          />
        </section>
        <TaskChatDrawer
          priority={chatTask}
          onClose={() => setChatTask(null)}
          onDone={() => {
            const t = chatTask;
            setChatTask(null);
            if (t) dismiss(t, 'relevant');
          }}
        />
      </>
    );
  }

  // Grid view — all remaining tasks
  return (
    <>
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
      <TaskChatDrawer
        priority={chatTask}
        onClose={() => setChatTask(null)}
        onDone={() => {
          const t = chatTask;
          setChatTask(null);
          if (t) dismiss(t, 'relevant');
        }}
      />
    </>
  );
}
