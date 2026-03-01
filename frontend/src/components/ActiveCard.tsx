import { type PriorityItem, type PriorityLevel } from '../lib/api/client';
import { formatDueDate } from '../lib/utils/dateUtils';
import { MOCK_BRIEFINGS, DEFAULT_BRIEFING, type TaskBriefing } from '../lib/mockBriefings';

// ── Shared styles ─────────────────────────────────────────────────────────────

interface PriorityStyles {
  badge: string;
  border: string;
  dueDateUrgent: string;
}

const PRIORITY_STYLES: Record<PriorityLevel, PriorityStyles> = {
  high: {
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
    border: 'border-red-500/20',
    dueDateUrgent: 'text-red-400',
  },
  medium: {
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    border: 'border-amber-500/20',
    dueDateUrgent: 'text-amber-400',
  },
  low: {
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    border: 'border-stone-700/60',
    dueDateUrgent: 'text-stone-400',
  },
};

// ── Action sections ───────────────────────────────────────────────────────────

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="w-full bg-stone-800 rounded-full h-1">
      <div
        className="bg-amber-400/70 h-1 rounded-full transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function GradingSection({ briefing }: { briefing: TaskBriefing }) {
  const { progress, previewRows, overflowLabel, source } = briefing;
  if (!progress) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
          {source}
        </span>
        <span className="text-stone-500 text-xs">
          {progress.done} / {progress.total} {progress.label}
        </span>
      </div>
      <ProgressBar done={progress.done} total={progress.total} />
      <div className="space-y-0.5 pt-1">
        {previewRows?.map((name) => (
          <div key={name} className="flex items-center justify-between py-1.5 border-b border-stone-800/60">
            <span className="text-stone-300 text-xs">{name}</span>
            <span className="text-stone-700 text-xs">○ not graded</span>
          </div>
        ))}
        {overflowLabel && (
          <p className="text-stone-700 text-xs pt-2">{overflowLabel}</p>
        )}
      </div>
    </div>
  );
}

function ReviewSection({ briefing }: { briefing: TaskBriefing }) {
  const { progress, previewRows, overflowLabel, source } = briefing;
  if (!progress) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
          {source}
        </span>
        <span className="text-stone-500 text-xs">
          {progress.done} / {progress.total} {progress.label}
        </span>
      </div>
      <ProgressBar done={progress.done} total={progress.total} />
      <div className="space-y-0.5 pt-1">
        {previewRows?.map((row) => (
          <div key={row} className="flex items-center justify-between py-1.5 border-b border-stone-800/60">
            <span className="text-stone-400 text-xs">{row}</span>
          </div>
        ))}
        {overflowLabel && (
          <p className="text-stone-600 text-xs pt-2">{overflowLabel}</p>
        )}
      </div>
    </div>
  );
}

function AttendanceSection({ briefing }: { briefing: TaskBriefing }) {
  const { progress, previewRows, overflowLabel, source } = briefing;
  if (!progress) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
          {source}
        </span>
        <span className="text-stone-500 text-xs">
          {progress.done} / {progress.total} {progress.label}
        </span>
      </div>
      <ProgressBar done={progress.done} total={progress.total} />
      <div className="space-y-0.5 pt-1">
        {previewRows?.map((name) => (
          <div key={name} className="flex items-center justify-between py-1.5 border-b border-stone-800/60">
            <span className="text-stone-300 text-xs">{name}</span>
            <span className="text-stone-700 text-xs">○ pending</span>
          </div>
        ))}
        {overflowLabel && (
          <p className="text-stone-700 text-xs pt-2">{overflowLabel}</p>
        )}
      </div>
    </div>
  );
}

function EmailDraftSection({ briefing }: { briefing: TaskBriefing }) {
  const { draft, source } = briefing;
  if (!draft) return null;

  return (
    <div className="space-y-2">
      <span className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
        Draft reply · {source}
      </span>
      <div className="bg-stone-950 border border-stone-800 rounded-xl p-4">
        <p className="text-stone-400 text-xs leading-relaxed whitespace-pre-line">{draft}</p>
      </div>
    </div>
  );
}

function ActionSection({ briefing }: { briefing: TaskBriefing }) {
  switch (briefing.actionType) {
    case 'grading':    return <GradingSection briefing={briefing} />;
    case 'review':     return <ReviewSection briefing={briefing} />;
    case 'attendance': return <AttendanceSection briefing={briefing} />;
    case 'email-draft':return <EmailDraftSection briefing={briefing} />;
    default:           return null;
  }
}

// ── ActiveCard ────────────────────────────────────────────────────────────────

interface ActiveCardProps {
  priority: PriorityItem;
  rank: number;
  onBack: () => void;
  onDone: () => void;
}

export function ActiveCard({ priority, rank, onBack, onDone }: ActiveCardProps) {
  const styles = PRIORITY_STYLES[priority.priority];
  const dueDate = formatDueDate(priority.due_date);
  const isUrgentDue = dueDate.isOverdue || dueDate.isDueToday;
  const briefing = MOCK_BRIEFINGS[priority.id] ?? DEFAULT_BRIEFING;

  return (
    <div className="space-y-5">

      {/* Nav bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-stone-600 hover:text-stone-400 text-xs font-medium flex items-center gap-1 transition-colors"
        >
          ← today
        </button>
        <button
          onClick={onDone}
          className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 px-3 py-1.5 rounded-lg hover:bg-emerald-500/10 border border-transparent hover:border-emerald-500/20 transition-all"
        >
          Mark done ✓
        </button>
      </div>

      {/* Card */}
      <div className={`bg-stone-900 rounded-2xl border ${styles.border} p-6 space-y-6`}>

        {/* Task header */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-stone-800 border border-stone-700 flex items-center justify-center text-xs font-bold text-stone-400">
              {rank}
            </span>
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${styles.badge}`}>
              {priority.priority}
            </span>
          </div>

          <h2 className="text-stone-100 font-semibold text-base leading-snug">
            {priority.title}
          </h2>

          <div className="flex flex-wrap gap-1.5 items-center">
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
            <span className={`text-xs font-medium ${isUrgentDue ? styles.dueDateUrgent : 'text-stone-600'}`}>
              {dueDate.label}
            </span>
          </div>
        </div>

        <div className="border-t border-stone-800" />

        {/* Marimba note */}
        <div className="flex gap-3 bg-amber-500/5 border border-amber-500/15 rounded-xl p-4">
          <span className="text-lg flex-shrink-0 mt-0.5">🦊</span>
          <p className="text-stone-400 text-sm leading-relaxed">
            {priority.marimba_note ?? briefing.marimbaNote}
          </p>
        </div>

        {/* Action-specific content */}
        <ActionSection briefing={briefing} />

        {/* Primary action button */}
        {briefing.actionType !== 'generic' && (
          <button className="w-full py-3 rounded-xl bg-stone-800 hover:bg-stone-700 border border-stone-700 hover:border-stone-600 text-stone-200 text-sm font-medium transition-all">
            {briefing.primaryActionLabel} →
          </button>
        )}

      </div>
    </div>
  );
}
