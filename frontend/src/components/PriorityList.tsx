import { type PriorityItem } from '../lib/api/client';
import { PriorityCard } from './PriorityCard';

interface PriorityListProps {
  priorities: PriorityItem[];
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

export function PriorityList({ priorities }: PriorityListProps) {
  return (
    <section aria-label="Your top priorities">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          Top {priorities.length} · Right Now
        </h2>
      </div>

      {priorities.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {priorities.map((priority, index) => (
            <PriorityCard key={priority.id} priority={priority} rank={index + 1} />
          ))}
        </div>
      )}
    </section>
  );
}
