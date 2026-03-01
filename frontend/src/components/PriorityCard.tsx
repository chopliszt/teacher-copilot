import { type PriorityItem, type PriorityLevel } from '../lib/api/client';
import { formatDueDate } from '../lib/utils/dateUtils';

interface PriorityStyles {
  badge: string;
  border: string;
  dueDateUrgent: string;
}

const PRIORITY_STYLES: Record<PriorityLevel, PriorityStyles> = {
  high: {
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
    border: 'border-red-500/15 hover:border-red-500/30',
    dueDateUrgent: 'text-red-400',
  },
  medium: {
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    border: 'border-amber-500/15 hover:border-amber-500/30',
    dueDateUrgent: 'text-amber-400',
  },
  low: {
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    border: 'border-stone-700/50 hover:border-stone-600',
    dueDateUrgent: 'text-stone-400',
  },
};

interface PriorityCardProps {
  priority: PriorityItem;
  rank: number;
  onStart: () => void;
}

export function PriorityCard({ priority, rank, onStart }: PriorityCardProps) {
  const styles = PRIORITY_STYLES[priority.priority];
  const dueDate = formatDueDate(priority.due_date);
  const isUrgentDue = dueDate.isOverdue || dueDate.isDueToday;

  return (
    <article
      className={`relative flex flex-col gap-4 bg-stone-900 rounded-2xl border ${styles.border} p-5 transition-colors`}
    >
      {/* Header: rank + urgency badge */}
      <div className="flex items-center justify-between">
        <span className="w-7 h-7 rounded-full bg-stone-800 border border-stone-700 flex items-center justify-center text-xs font-bold text-stone-400">
          {rank}
        </span>
        <span
          className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${styles.badge}`}
        >
          {priority.priority}
        </span>
      </div>

      {/* Task title */}
      <h2 className="text-stone-100 font-semibold text-sm leading-snug flex-1">
        {priority.title}
      </h2>

      {/* Metadata chips */}
      <div className="flex flex-wrap gap-1.5">
        {priority.class && priority.class !== 'All' && (
          <span className="bg-stone-800 text-stone-400 text-xs px-2.5 py-1 rounded-full border border-stone-700/60">
            {priority.class}
          </span>
        )}
        {priority.subject && (
          <span className="bg-stone-800 text-stone-400 text-xs px-2.5 py-1 rounded-full border border-stone-700/60">
            {priority.subject}
          </span>
        )}
        <span className="bg-stone-800 text-stone-400 text-xs px-2.5 py-1 rounded-full border border-stone-700/60">
          ⏱ {priority.estimated_time}
        </span>
      </div>

      {/* Footer: due date + action */}
      <div className="flex items-center justify-between pt-3 border-t border-stone-800 mt-auto">
        <span
          className={`text-xs font-medium ${isUrgentDue ? styles.dueDateUrgent : 'text-stone-600'}`}
        >
          {dueDate.label}
        </span>
        <button
          onClick={onStart}
          className="text-xs font-semibold text-amber-400 hover:text-amber-300 px-3 py-1.5 rounded-lg hover:bg-amber-500/10 border border-transparent hover:border-amber-500/20 transition-all"
          aria-label={`Start task: ${priority.title}`}
        >
          Start →
        </button>
      </div>
    </article>
  );
}
