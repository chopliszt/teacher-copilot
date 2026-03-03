import { useState, useEffect } from 'react';
import { useSchedule } from '../lib/hooks/useSchedule';
import { useAbsences } from '../lib/hooks/useAbsences';
import { useWeeklySchedule } from '../lib/hooks/useWeeklySchedule';
import { useLastSession, useLogSession } from '../lib/hooks/useClassSession';
import { type SchedulePeriod, type Absence, type ClassDisruption } from '../lib/api/client';
import { MOCK_CLASS_BRIEFINGS, DEFAULT_CLASS_BRIEFING, type ClassBriefing } from '../lib/mockClassBriefings';

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupIsAffected(disruption: ClassDisruption, group: string): boolean {
  return disruption.groups_affected.some(
    (g) => g.toLowerCase() === 'all' || g === group
  );
}

// ── Class briefing panel ──────────────────────────────────────────────────────

interface BriefingPanelProps {
  period: SchedulePeriod;
  absentStudents: Absence[];
  disruptions: ClassDisruption[];
  onClose: () => void;
}

function BriefingPanel({ period, absentStudents, disruptions, onClose }: BriefingPanelProps) {
  const raw = MOCK_CLASS_BRIEFINGS[period.group];
  const briefing: ClassBriefing = raw ?? {
    ...DEFAULT_CLASS_BRIEFING,
    group: period.group,
    subject: period.subject,
  };

  const totalFlags = absentStudents.length + briefing.flags;

  // Session log state
  const { data: lastSession, isLoading: sessionLoading } = useLastSession(period.group);
  const logSession = useLogSession(period.group);
  const [formOpen, setFormOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const [whatWorked, setWhatWorked] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    logSession.mutate(
      { notes, what_worked: whatWorked || undefined },
      {
        onSuccess: () => {
          setSaved(true);
          setFormOpen(false);
          setNotes('');
          setWhatWorked('');
          setTimeout(() => setSaved(false), 2000);
        },
      },
    );
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

      {/* Disruption block — shown first if present */}
      {disruptions.length > 0 && (
        <div className="bg-amber-500/8 border border-amber-500/25 rounded-xl px-4 py-3 space-y-2">
          <p className="text-amber-400/80 text-xs font-semibold uppercase tracking-wide">
            Today's disruption
          </p>
          {disruptions.map((d, i) => (
            <div key={i}>
              <p className="text-amber-100 text-sm">{d.description}</p>
              <p className="text-amber-400/60 text-xs mt-0.5">{d.time}</p>
            </div>
          ))}
        </div>
      )}

      {/* Quick stats */}
      <div className="flex gap-3 flex-wrap">
        <span className="bg-stone-800 border border-stone-700/60 text-stone-400 text-xs px-2.5 py-1 rounded-full">
          {briefing.studentCount} students
        </span>
        {absentStudents.length > 0 && (
          <span className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs px-2.5 py-1 rounded-full">
            {absentStudents.length} absent
          </span>
        )}
        {totalFlags > 0 ? (
          <span className="bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs px-2.5 py-1 rounded-full">
            {briefing.flags} flag{briefing.flags !== 1 ? 's' : ''}
          </span>
        ) : (
          <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs px-2.5 py-1 rounded-full">
            no flags
          </span>
        )}
      </div>

      {/* Absent students */}
      {absentStudents.length > 0 && (
        <div className="bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3 space-y-1">
          <p className="text-red-400/70 text-xs font-semibold uppercase tracking-wide mb-2">Absent today</p>
          {absentStudents.map((a) => (
            <p key={a.id} className="text-stone-300 text-sm">{a.student_name}</p>
          ))}
        </div>
      )}

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
          {sessionLoading ? (
            <span className="text-stone-700 text-xs italic">Loading…</span>
          ) : lastSession ? (
            <span className="text-stone-400">{lastSession.notes}</span>
          ) : (
            <span className="text-stone-500 italic">{briefing.lastSession}</span>
          )}
        </div>
      </div>

      {/* Source links + plan lesson */}
      <div className="flex gap-2 pt-1 flex-wrap">
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
        <button className="text-xs text-amber-600/70 hover:text-amber-400 border border-amber-500/20 hover:border-amber-500/40 px-3 py-1.5 rounded-lg transition-colors">
          Plan lesson →
        </button>
      </div>

      {/* Log session */}
      {!formOpen ? (
        <button
          onClick={() => setFormOpen(true)}
          className="w-full text-xs text-stone-600 hover:text-stone-400 border border-stone-800 hover:border-stone-700 px-3 py-2 rounded-lg transition-colors text-left"
        >
          {saved ? '✓ Session logged' : '+ Log this session'}
        </button>
      ) : (
        <div className="space-y-3 pt-1">
          <p className="text-stone-500 text-xs font-semibold uppercase tracking-wide">Log this session</p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="How did this class go?"
            rows={3}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
          />
          <textarea
            value={whatWorked}
            onChange={(e) => setWhatWorked(e.target.value)}
            placeholder="What worked well? (optional)"
            rows={2}
            className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={!notes.trim() || logSession.isPending}
              className="flex-1 py-2 rounded-xl bg-stone-700 hover:bg-stone-600 disabled:opacity-40 disabled:cursor-not-allowed text-stone-200 text-xs font-medium transition-all"
            >
              {logSession.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => { setFormOpen(false); setNotes(''); setWhatWorked(''); }}
              className="px-4 py-2 rounded-xl border border-stone-800 hover:border-stone-700 text-stone-600 hover:text-stone-400 text-xs transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

// ── Period chip ───────────────────────────────────────────────────────────────

interface PeriodChipProps {
  period: SchedulePeriod;
  isActive: boolean;
  absenceCount: number;
  hasDisruption: boolean;
  onClick: () => void;
}

function PeriodChip({ period, isActive, absenceCount, hasDisruption, onClick }: PeriodChipProps) {
  const base = 'relative flex-shrink-0 text-left rounded-xl px-3 py-2 min-w-[100px] border transition-colors';

  const color = isActive
    ? hasDisruption
      ? 'bg-amber-500/15 border-amber-500/50'
      : 'bg-stone-800 border-stone-600'
    : hasDisruption
      ? 'bg-amber-500/8 border-amber-500/30 hover:border-amber-500/50'
      : 'bg-stone-900 border-stone-800 hover:border-stone-700';

  return (
    <button onClick={onClick} className={`${base} ${color}`}>
      {absenceCount > 0 && (
        <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-red-400" />
      )}
      <p className={`text-xs font-semibold ${hasDisruption ? 'text-amber-100' : 'text-stone-200'}`}>
        {period.group}
      </p>
      <p className="text-stone-500 text-xs mt-0.5">{period.time}</p>
      {period.room && (
        <p className="text-stone-700 text-xs">{period.room}</p>
      )}
    </button>
  );
}

// ── TodaySchedule ─────────────────────────────────────────────────────────────

interface TodayScheduleProps {
  openGroup?: string | null;       // voice-triggered: open this group's briefing
  closeAllCounter?: number;        // increments on close_all action
}

export function TodaySchedule({ openGroup, closeAllCounter = 0 }: TodayScheduleProps) {
  const { data: schedule, isLoading } = useSchedule();
  const { data: absences = [] } = useAbsences();
  const { data: weeklySchedule } = useWeeklySchedule();
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  // Respond to voice-triggered group opens
  useEffect(() => {
    if (openGroup) setSelectedGroup(openGroup);
  }, [openGroup]);

  // Respond to close_all — clear internal state
  useEffect(() => {
    if (closeAllCounter > 0) setSelectedGroup(null);
  }, [closeAllCounter]);

  if (isLoading || !schedule) return null;

  const forcedDay = import.meta.env.VITE_MOCK_SCHEDULE_DAY
    ? parseInt(import.meta.env.VITE_MOCK_SCHEDULE_DAY as string, 10)
    : null;

  const jsDay = new Date().getDay();
  const isWeekend = forcedDay === null && (jsDay === 0 || jsDay === 6);
  const currentDay = forcedDay ?? schedule.current_day;

  const todayEntry = schedule.classes.find((day) => day.day === currentDay);
  const periodsToday = isWeekend ? [] : (todayEntry?.periods ?? []);

  // Disruptions that apply to today's schedule day
  const todayDisruptions: ClassDisruption[] = (weeklySchedule?.class_disruptions ?? [])
    .filter((d) => d.schedule_day === currentDay);

  const disruptionCount = todayDisruptions.length;

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
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-1.5 h-1.5 rounded-full ${disruptionCount > 0 ? 'bg-amber-500/60' : 'bg-stone-600'}`} />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          {sectionLabel}
        </h2>
      </div>

      {/* Disruption subtitle — only when there's something today */}
      {disruptionCount > 0 && (
        <p className="text-amber-500/60 text-xs mb-3 pl-3.5">
          {disruptionCount === 1
            ? `1 disruption · tap a class to see details`
            : `${disruptionCount} disruptions · tap a class to see details`}
        </p>
      )}
      {disruptionCount === 0 && <div className="mb-3" />}

      {periodsToday.length > 0 ? (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {periodsToday.map((period, index) => {
              const groupAbsences = absences.filter((a) => a.group_name === period.group);
              const groupDisruptions = todayDisruptions.filter((d) =>
                groupIsAffected(d, period.group)
              );
              return (
                <PeriodChip
                  key={`${period.group}-${index}`}
                  period={period}
                  isActive={selectedGroup === period.group}
                  absenceCount={groupAbsences.length}
                  hasDisruption={groupDisruptions.length > 0}
                  onClick={() => handleChipClick(period.group)}
                />
              );
            })}
          </div>

          {selectedPeriod && (
            <BriefingPanel
              period={selectedPeriod}
              absentStudents={absences.filter((a) => a.group_name === selectedPeriod.group)}
              disruptions={todayDisruptions.filter((d) =>
                groupIsAffected(d, selectedPeriod.group)
              )}
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
