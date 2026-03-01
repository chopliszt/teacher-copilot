import { useState } from 'react';
import { useSchedule } from '../lib/hooks/useSchedule';
import { type SchedulePeriod } from '../lib/api/client';
import { MOCK_CLASS_BRIEFINGS, DEFAULT_CLASS_BRIEFING, type ClassBriefing } from '../lib/mockClassBriefings';

// ── Class briefing panel ──────────────────────────────────────────────────────

interface BriefingPanelProps {
  period: SchedulePeriod;
  onClose: () => void;
}

function BriefingPanel({ period, onClose }: BriefingPanelProps) {
  const raw = MOCK_CLASS_BRIEFINGS[period.group];
  const briefing: ClassBriefing = raw ?? {
    ...DEFAULT_CLASS_BRIEFING,
    group: period.group,
    subject: period.subject,
  };

  return (
    <div className="mt-3 bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-4">

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-stone-100 font-semibold text-sm">{briefing.group}</p>
          <p className="text-stone-500 text-xs mt-0.5">
            {period.subject} · {period.time}{period.room ? ` · ${period.room}` : ''}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-stone-700 hover:text-stone-500 text-xs transition-colors flex-shrink-0 mt-0.5"
          aria-label="Close briefing"
        >
          ✕
        </button>
      </div>

      {/* Quick stats */}
      <div className="flex gap-3">
        <span className="bg-stone-800 border border-stone-700/60 text-stone-400 text-xs px-2.5 py-1 rounded-full">
          {briefing.studentCount} students
        </span>
        {briefing.flags > 0 ? (
          <span className="bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs px-2.5 py-1 rounded-full">
            {briefing.flags} flag{briefing.flags !== 1 ? 's' : ''}
          </span>
        ) : (
          <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs px-2.5 py-1 rounded-full">
            no flags
          </span>
        )}
      </div>

      <div className="border-t border-stone-800" />

      {/* Marimba note */}
      <div className="flex gap-3">
        <span className="text-base flex-shrink-0 mt-0.5">🦊</span>
        <p className="text-stone-400 text-sm leading-relaxed">{briefing.marimbaNote}</p>
      </div>

      {/* Current unit + last session */}
      <div className="space-y-2 text-xs">
        <div className="flex gap-2">
          <span className="text-stone-600 w-20 flex-shrink-0">Unit</span>
          <span className="text-stone-400">{briefing.unit}</span>
        </div>
        <div className="flex gap-2">
          <span className="text-stone-600 w-20 flex-shrink-0">Last session</span>
          <span className="text-stone-400">{briefing.lastSession}</span>
        </div>
      </div>

      {/* Source links (mocked) */}
      <div className="flex gap-2 pt-1">
        {briefing.sources.includes('Toddle') && (
          <button className="text-xs text-stone-600 hover:text-stone-400 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-colors">
            Toddle →
          </button>
        )}
        {briefing.sources.includes('Google Sheets') && (
          <button className="text-xs text-stone-600 hover:text-stone-400 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-colors">
            Student list →
          </button>
        )}
      </div>

    </div>
  );
}

// ── Period chip ───────────────────────────────────────────────────────────────

interface PeriodChipProps {
  period: SchedulePeriod;
  isActive: boolean;
  onClick: () => void;
}

function PeriodChip({ period, isActive, onClick }: PeriodChipProps) {
  return (
    <button
      onClick={onClick}
      className={`
        flex-shrink-0 text-left rounded-xl px-3 py-2 min-w-[100px]
        border transition-colors
        ${isActive
          ? 'bg-stone-800 border-stone-600'
          : 'bg-stone-900 border-stone-800 hover:border-stone-700'
        }
      `}
    >
      <p className="text-stone-200 text-xs font-semibold">{period.group}</p>
      <p className="text-stone-500 text-xs mt-0.5">{period.time}</p>
      {period.room && (
        <p className="text-stone-700 text-xs">{period.room}</p>
      )}
    </button>
  );
}

// ── TodaySchedule ─────────────────────────────────────────────────────────────

export function TodaySchedule() {
  const { data: schedule, isLoading } = useSchedule();
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  if (isLoading || !schedule) return null;

  // VITE_MOCK_SCHEDULE_DAY overrides the live day — for dev/testing only.
  const forcedDay = import.meta.env.VITE_MOCK_SCHEDULE_DAY
    ? parseInt(import.meta.env.VITE_MOCK_SCHEDULE_DAY as string, 10)
    : null;

  const jsDay = new Date().getDay();
  const isWeekend = forcedDay === null && (jsDay === 0 || jsDay === 6);
  const currentDay = forcedDay ?? schedule.current_day;

  const todayEntry = schedule.classes.find((day) => day.day === currentDay);
  const periodsToday = isWeekend ? [] : (todayEntry?.periods ?? []);

  const dayLabel = isWeekend ? 'Weekend' : `Day ${currentDay}`;

  const sectionLabel = periodsToday.length > 0
    ? `Today's Classes · ${dayLabel} · ${periodsToday.length} period${periodsToday.length !== 1 ? 's' : ''}`
    : `Today's Classes · ${dayLabel}`;

  const selectedPeriod = periodsToday.find((p) => p.group === selectedGroup) ?? null;

  const handleChipClick = (group: string) => {
    setSelectedGroup((prev) => (prev === group ? null : group));
  };

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1.5 h-1.5 rounded-full bg-stone-600" />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          {sectionLabel}
        </h2>
      </div>

      {periodsToday.length > 0 ? (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {periodsToday.map((period, index) => (
              <PeriodChip
                key={`${period.group}-${index}`}
                period={period}
                isActive={selectedGroup === period.group}
                onClick={() => handleChipClick(period.group)}
              />
            ))}
          </div>

          {selectedPeriod && (
            <BriefingPanel
              period={selectedPeriod}
              onClose={() => setSelectedGroup(null)}
            />
          )}
        </>
      ) : (
        <p className="text-stone-700 text-sm">
          {isWeekend ? 'Enjoy the rest.' : 'No classes scheduled today.'}
        </p>
      )}
    </div>
  );
}
