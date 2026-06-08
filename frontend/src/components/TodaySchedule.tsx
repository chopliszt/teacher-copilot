import { useState, useEffect } from 'react';
import { useSchedule } from '../lib/hooks/useSchedule';
import { useAbsences } from '../lib/hooks/useAbsences';
import { useWeeklySchedule } from '../lib/hooks/useWeeklySchedule';
import { useLastSession, useLogSession } from '../lib/hooks/useClassSession';
import { useStudentFlags } from '../lib/hooks/useStudentFlags';
import { useEvents, useUpcomingEvents, useDismissEvent } from '../lib/hooks/useEvents';
import { type SchedulePeriod, type Absence, type ClassDisruption, type CalendarEvent } from '../lib/api/client';
import { LessonPlanDrawer } from './LessonPlanDrawer';
import { EventChatDrawer } from './EventChatDrawer';

// "Coming up" date label: "Tomorrow" for the next day, else a short weekday.
function upcomingDateLabel(dateStr: string, today: string): string {
  const target = new Date(`${dateStr}T00:00:00`);
  const base = new Date(`${today}T00:00:00`);
  const diffDays = Math.round((target.getTime() - base.getTime()) / 86_400_000);
  if (diffDays === 1) return 'Tomorrow';
  return target.toLocaleDateString(undefined, { weekday: 'short' });
}

// Summary of an event, sent to Marimba when the teacher taps 🦊 so she knows
// which meeting "this" is — and can answer grounded questions about it (who sent
// it, who's coming) without searching. Mirrors the text-chat event context.
function eventFocusSummary(event: CalendarEvent): string {
  const when = event.start_time
    ? ` at ${event.start_time}${event.end_time ? `–${event.end_time}` : ''}`
    : '';
  const parts = [`${event.title} — ${event.date}${when}`];
  if (event.location) parts.push(`Location: ${event.location}`);
  if (event.organizer) parts.push(`Organized / sent by: ${event.organizer}`);
  if (event.attendees.length > 0) parts.push(`Attendees: ${event.attendees.join(', ')}`);
  return parts.join('. ');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupIsAffected(disruption: ClassDisruption, group: string): boolean {
  return disruption.groups_affected.some(
    (g) => g.toLowerCase() === 'all' || g === group
  );
}

// Parse the START of a time string into minutes-since-midnight so classes and
// events sort into one timeline. Handles class ranges ("11:30am - 12:50pm",
// take the start) and 24h event times ("12:00"). Unknown → sorts last.
function parseStartMinutes(timeStr: string): number {
  const start = timeStr.split('-')[0].trim();
  const match = start.match(/^(\d{1,2}):(\d{2})\s*(am|pm)?$/i);
  if (!match) return Number.MAX_SAFE_INTEGER;
  let hour = parseInt(match[1], 10);
  const minute = parseInt(match[2], 10);
  const meridiem = match[3]?.toLowerCase();
  if (meridiem === 'pm' && hour !== 12) hour += 12;
  if (meridiem === 'am' && hour === 12) hour = 0;
  return hour * 60 + minute;
}

// ── Class briefing panel ──────────────────────────────────────────────────────

interface BriefingPanelProps {
  period: SchedulePeriod;
  absentStudents: Absence[];
  disruptions: ClassDisruption[];
  onClose: () => void;
  autoOpenPlanNonce?: number;   // voice "plan the lesson for X" — opens the drawer
}

function BriefingPanel({ period, absentStudents, disruptions, onClose, autoOpenPlanNonce }: BriefingPanelProps) {
  // Session log state
  const { data: lastSession, isLoading: sessionLoading } = useLastSession(period.group);
  const logSession = useLogSession(period.group);
  const [formOpen, setFormOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const [whatWorked, setWhatWorked] = useState('');
  const [saved, setSaved] = useState(false);

  // Student flags for this group — pulled from data/student_flags.json
  const { data: allFlags } = useStudentFlags();
  const flagsForGroup = allFlags?.[period.group] ?? [];

  // Lesson plan drawer state — null = closed, group string = open for that group
  const [planLessonGroup, setPlanLessonGroup] = useState<string | null>(null);
  const [planInitialTab, setPlanInitialTab] = useState<'plan' | 'history'>('plan');

  // Voice-triggered: when the nonce changes, open this group's lesson-plan drawer.
  useEffect(() => {
    if (autoOpenPlanNonce) {
      // Syncing UI to an external voice signal (a nonce), not a render cascade.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlanInitialTab('plan');
      setPlanLessonGroup(period.group);
    }
  }, [autoOpenPlanNonce, period.group]);

  // Expandable flag list — hidden by default so the panel stays tidy when
  // there are many flagged students (e.g. 7B has 5).
  const [flagsExpanded, setFlagsExpanded] = useState(false);

  // The backend upserts the session note by "{group}_{today}_{schedule_day}",
  // so re-saving overwrites today's note rather than creating a duplicate.
  // We only treat the panel as "editing" when lastSession is actually from
  // today — otherwise lastSession is an older note and saving would write a
  // brand-new today row, so prefilling it would be misleading.
  // en-CA gives YYYY-MM-DD in *local* time, matching the backend's date.today().
  const today = new Date().toLocaleDateString('en-CA');
  const editingToday = !!lastSession && lastSession.date === today;

  // Open the form, prefilling with today's note if one already exists so the
  // teacher can see and correct what's there (no blank-slate guessing).
  const openForm = () => {
    if (editingToday && lastSession) {
      setNotes(lastSession.notes);
      setWhatWorked(lastSession.what_worked ?? '');
    }
    setFormOpen(true);
  };

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
          <p className="text-stone-100 font-semibold text-sm">{period.group}</p>
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

      {/* Quick stats — all real now */}
      <div className="flex gap-3 flex-wrap">
        {absentStudents.length > 0 && (
          <span className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs px-2.5 py-1 rounded-full">
            {absentStudents.length} absent
          </span>
        )}
        {flagsForGroup.length > 0 ? (
          <button
            onClick={() => setFlagsExpanded((v) => !v)}
            className="bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/15 text-xs px-2.5 py-1 rounded-full transition-colors"
            title="Tap to see who needs support"
          >
            {flagsForGroup.length} need{flagsForGroup.length === 1 ? 's' : ''} support
            <span className="ml-1 text-amber-400/60">{flagsExpanded ? '▾' : '▸'}</span>
          </button>
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

      {/* Flagged students — only shown after the chip is tapped */}
      {flagsExpanded && flagsForGroup.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/15 rounded-xl px-4 py-3 space-y-1.5">
          <p className="text-amber-400/70 text-xs font-semibold uppercase tracking-wide mb-2">
            Students needing support
          </p>
          {flagsForGroup.map((f) => (
            <div key={f.name} className="text-xs">
              <p className="text-stone-200">{f.name}</p>
              {f.notes && (
                <p className="text-stone-500 text-[0.7rem]">{f.notes}</p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="border-t border-stone-800" />

      {/* Last session — real DB data, or empty state */}
      <div className="space-y-2 text-xs">
        <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
          Last session
        </p>
        {sessionLoading ? (
          <p className="text-stone-700 italic">Loading…</p>
        ) : lastSession ? (
          <div className="space-y-1">
            <p className="text-stone-300 text-sm leading-relaxed">{lastSession.notes}</p>
            {lastSession.what_worked && (
              <p className="text-stone-500 text-xs italic">
                Lo que funcionó: {lastSession.what_worked}
              </p>
            )}
            <p className="text-stone-700 text-[0.65rem]">{lastSession.date}</p>
          </div>
        ) : (
          <p className="text-stone-700 italic text-xs">
            Sin registro todavía. Después de la clase, usá <span className="text-stone-500">+ Log this session</span> de abajo.
          </p>
        )}
      </div>

      {/* Plan lesson / History */}
      <div className="flex gap-2 pt-1 flex-wrap">
        <button
          onClick={() => { setPlanInitialTab('plan'); setPlanLessonGroup(period.group); }}
          className="text-xs text-amber-600/70 hover:text-amber-400 border border-amber-500/20 hover:border-amber-500/40 px-3 py-1.5 rounded-lg transition-colors"
        >
          Plan lesson →
        </button>
        <button
          onClick={() => { setPlanInitialTab('history'); setPlanLessonGroup(period.group); }}
          className="text-xs text-stone-500 hover:text-stone-300 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-colors"
        >
          History →
        </button>
      </div>

      {/* Log session */}
      {!formOpen ? (
        <button
          onClick={openForm}
          className="w-full text-xs text-stone-600 hover:text-stone-400 border border-stone-800 hover:border-stone-700 px-3 py-2 rounded-lg transition-colors text-left"
        >
          {saved ? '✓ Session logged' : editingToday ? '✎ Edit today’s note' : '+ Log this session'}
        </button>
      ) : (
        <div className="space-y-3 pt-1">
          <p className="text-stone-500 text-xs font-semibold uppercase tracking-wide">
            {editingToday ? 'Edit today’s note' : 'Log this session'}
          </p>
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

      {/* Lesson plan drawer — opens on "Plan lesson →" or "History →" click */}
      <LessonPlanDrawer
        group={planLessonGroup}
        initialTab={planInitialTab}
        onClose={() => setPlanLessonGroup(null)}
      />

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

// ── Event chip ──────────────────────────────────────────────────────────────
// A meeting/event in the timeline. Distinguished from a class by amber tone + a
// calendar icon + position (never color alone — dyslexia / colorblind safe).
// Carries the quiet × dismiss in its top corner.

function CalendarIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

interface EventChipProps {
  event: CalendarEvent;
  isActive: boolean;
  onClick: () => void;
  onDismiss: () => void;
}

function EventChip({ event, isActive, onClick, onDismiss }: EventChipProps) {
  const base = 'relative flex-shrink-0 text-left rounded-xl pl-3 pr-6 py-2 min-w-[100px] border transition-colors';
  const color = isActive
    ? 'bg-amber-500/20 border-amber-500/60'
    : 'bg-amber-500/8 border-amber-500/30 hover:border-amber-500/50';

  const timeLabel = event.start_time
    ? `${event.start_time}${event.end_time ? `–${event.end_time}` : ''}`
    : 'all day';

  return (
    <div className="relative flex-shrink-0">
      <button onClick={onClick} className={`${base} ${color}`}>
        <div className="flex items-center gap-1 text-amber-300">
          <CalendarIcon />
          <p className="text-xs font-semibold text-amber-100 truncate max-w-[88px]">{event.title}</p>
        </div>
        <p className="text-amber-400/60 text-xs mt-0.5">{timeLabel}</p>
        {event.location && (
          <p className="text-amber-400/40 text-xs truncate max-w-[100px]">{event.location}</p>
        )}
      </button>
      {/* Quiet × — dismiss is a relevance signal, not a delete (event stays findable) */}
      <button
        onClick={(e) => { e.stopPropagation(); onDismiss(); }}
        aria-label={`Dismiss ${event.title}`}
        className="absolute top-1 right-1 text-amber-500/40 hover:text-amber-200 text-xs leading-none transition-colors"
      >
        ✕
      </button>
    </div>
  );
}

// ── Event card (expanded) ─────────────────────────────────────────────────────
// Progressive disclosure: the chip shows time + title; tapping reveals the rest.
// Physical location is primary; the Meet link is a secondary line. (The two
// "talk about this" actions are wired in the next step.)

interface EventCardProps {
  event: CalendarEvent;
  onClose: () => void;
  onChat: () => void;
  onVoice: () => void;
}

function EventCard({ event, onClose, onChat, onVoice }: EventCardProps) {
  const timeLabel = event.start_time
    ? `${event.start_time}${event.end_time ? `–${event.end_time}` : ''}`
    : 'All day';

  return (
    <div className="mt-3 bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-stone-100 font-semibold text-sm">{event.title}</p>
          <p className="text-stone-500 text-xs mt-0.5">
            {timeLabel}{event.location ? ` · ${event.location}` : ''}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-stone-700 hover:text-stone-500 text-xs transition-colors flex-shrink-0 mt-0.5"
          aria-label="Close event"
        >
          ✕
        </button>
      </div>

      {event.organizer && (
        <p className="text-stone-400 text-xs">Organized by {event.organizer}</p>
      )}

      {event.attendees.length > 0 && (
        <p className="text-stone-400 text-xs">with {event.attendees.join(', ')}</p>
      )}

      {event.meet_link && (
        <a
          href={event.meet_link}
          target="_blank"
          rel="noreferrer"
          className="inline-block text-xs text-stone-500 hover:text-stone-300 transition-colors"
        >
          Video link →
        </a>
      )}

      <p className="text-stone-700 text-[0.65rem]">
        from {event.source}{event.updated_at ? ' · updated' : ''}
      </p>

      {/* Two ways to talk about it — same intent, two modes. No task buttons. */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={onChat}
          className="text-xs text-amber-600/70 hover:text-amber-400 border border-amber-500/20 hover:border-amber-500/40 px-3 py-1.5 rounded-lg transition-colors"
        >
          Chat about this →
        </button>
        <button
          onClick={onVoice}
          aria-label="Talk to Marimba about this event"
          className="text-sm border border-stone-800 hover:border-stone-700 px-2.5 py-1.5 rounded-lg transition-colors"
          title="Talk to Marimba about this"
        >
          🦊
        </button>
      </div>
    </div>
  );
}

// ── TodaySchedule ─────────────────────────────────────────────────────────────

interface TodayScheduleProps {
  openGroup?: string | null;       // voice-triggered: open this group's briefing
  closeAllCounter?: number;        // increments on close_all action
  peekRequest?: { offset: number; nonce: number } | null;   // voice "show tomorrow"
  openLessonPlan?: { group: string; nonce: number } | null; // voice "plan lesson for X"
  onVoiceAboutEvent?: (focus: string) => void;              // 🦊 on an event chip
}

export function TodaySchedule({ openGroup, closeAllCounter = 0, peekRequest, openLessonPlan, onVoiceAboutEvent }: TodayScheduleProps) {
  const { data: schedule, isLoading } = useSchedule();
  const { data: absences = [] } = useAbsences();
  const { data: weeklySchedule } = useWeeklySchedule();
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [chatEvent, setChatEvent] = useState<CalendarEvent | null>(null);
  const [peekOffset, setPeekOffset] = useState(0);

  // en-CA gives YYYY-MM-DD in local time, matching the backend's date.today().
  const today = new Date().toLocaleDateString('en-CA');
  const { data: eventsData } = useEvents(today);
  const { data: upcomingData } = useUpcomingEvents(today, 2);
  const dismissEvent = useDismissEvent();

  // Respond to voice-triggered group opens — always snap back to today
  useEffect(() => {
    if (openGroup) {
      setPeekOffset(0);
      setSelectedGroup(openGroup);
      setSelectedEventId(null);
    }
  }, [openGroup]);

  // Respond to close_all — clear internal state
  useEffect(() => {
    if (closeAllCounter > 0) {
      setSelectedGroup(null);
      setSelectedEventId(null);
      setPeekOffset(0);
    }
  }, [closeAllCounter]);

  // Voice "show me tomorrow/yesterday/day N" — jump the peek to that offset.
  useEffect(() => {
    if (peekRequest) {
      setPeekOffset(peekRequest.offset);
      setSelectedGroup(null);
      setSelectedEventId(null);
    }
    // Keyed on the nonce only — the request object itself is intentionally
    // omitted so the jump fires once per voice command, not on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [peekRequest?.nonce]);

  // Voice "plan the lesson for X" — snap to today and select that group so its
  // BriefingPanel mounts; the panel then auto-opens the lesson-plan drawer.
  useEffect(() => {
    if (openLessonPlan) {
      setPeekOffset(0);
      setSelectedGroup(openLessonPlan.group);
    }
    // Keyed on the nonce only — the request object itself is intentionally
    // omitted so the drawer opens once per voice command, not on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openLessonPlan?.nonce]);

  if (isLoading || !schedule) return null;

  const forcedDay = import.meta.env.VITE_MOCK_SCHEDULE_DAY
    ? parseInt(import.meta.env.VITE_MOCK_SCHEDULE_DAY as string, 10)
    : null;

  const jsDay = new Date().getDay();
  const isWeekend = forcedDay === null && (jsDay === 0 || jsDay === 6);
  const currentDay = forcedDay ?? schedule.current_day;

  // Peek: compute which schedule day to display (wraps 1–6)
  const displayDay = peekOffset === 0
    ? currentDay
    : ((currentDay - 1 + peekOffset) % 6 + 6) % 6 + 1;

  const displayEntry = schedule.classes.find((d) => d.day === displayDay);
  const periodsDisplay = (isWeekend && peekOffset === 0) ? [] : (displayEntry?.periods ?? []);

  const displayDisruptions: ClassDisruption[] = (weeklySchedule?.class_disruptions ?? [])
    .filter((d) => d.schedule_day === displayDay);

  const disruptionCount = displayDisruptions.length;

  const handlePeek = (delta: number) => {
    setPeekOffset((prev) => prev + delta);
    setSelectedGroup(null);
  };

  const dayLabel = (isWeekend && peekOffset === 0) ? 'Weekend' : `Day ${displayDay}`;
  const peekLabel = peekOffset === 0
    ? "Today's Classes"
    : peekOffset === 1 ? 'Tomorrow'
    : peekOffset === -1 ? 'Yesterday'
    : `${peekOffset > 0 ? 'In' : ''} ${Math.abs(peekOffset)} days`;

  const sectionLabel = periodsDisplay.length > 0
    ? `${peekLabel} · ${dayLabel} · ${periodsDisplay.length} period${periodsDisplay.length !== 1 ? 's' : ''}`
    : `${peekLabel} · ${dayLabel}`;

  const selectedPeriod = periodsDisplay.find((p) => p.group === selectedGroup) ?? null;

  // Events only map cleanly to TODAY's calendar date, so only merge them when
  // we're viewing today (not a peeked rotation day).
  const eventsToday: CalendarEvent[] = peekOffset === 0 ? (eventsData?.events ?? []) : [];
  const upcomingEvents: CalendarEvent[] = peekOffset === 0 ? (upcomingData?.events ?? []) : [];
  // Selection is shared across today's chips and the "Coming up" list.
  const selectedEvent =
    [...eventsToday, ...upcomingEvents].find((e) => e.id === selectedEventId) ?? null;

  const handleChipClick = (group: string) => {
    setSelectedEventId(null);
    setSelectedGroup((prev) => (prev === group ? null : group));
  };

  const handleEventClick = (id: string) => {
    setSelectedGroup(null);
    setSelectedEventId((prev) => (prev === id ? null : id));
  };

  // One time-ordered timeline of classes + events. Each carries its sort key
  // (minutes since midnight) so a meeting at noon sits between the morning and
  // afternoon classes.
  type TimelineItem =
    | { kind: 'class'; period: SchedulePeriod; index: number; sortKey: number }
    | { kind: 'event'; event: CalendarEvent; sortKey: number };

  const timelineItems: TimelineItem[] = [
    ...periodsDisplay.map((period, index) => ({
      kind: 'class' as const,
      period,
      index,
      sortKey: parseStartMinutes(period.time),
    })),
    ...eventsToday.map((event) => ({
      kind: 'event' as const,
      event,
      sortKey: event.start_time ? parseStartMinutes(event.start_time) : 0,
    })),
  ].sort((a, b) => a.sortKey - b.sortKey);

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${disruptionCount > 0 ? 'bg-amber-500/60' : 'bg-stone-600'}`} />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase flex-1">
          {sectionLabel}
        </h2>
        {/* Peek arrows */}
        <div className="flex items-center gap-1 ml-auto">
          <button
            onClick={() => handlePeek(-1)}
            aria-label="Previous day"
            className="text-stone-700 hover:text-stone-400 transition-colors p-0.5"
          >
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="7 1 3 5.5 7 10" />
            </svg>
          </button>
          {peekOffset !== 0 && (
            <button
              onClick={() => { setPeekOffset(0); setSelectedGroup(null); }}
              className="text-stone-600 hover:text-stone-400 text-xs transition-colors px-1"
            >
              today
            </button>
          )}
          <button
            onClick={() => handlePeek(1)}
            aria-label="Next day"
            className="text-stone-700 hover:text-stone-400 transition-colors p-0.5"
          >
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="4 1 8 5.5 4 10" />
            </svg>
          </button>
        </div>
      </div>

      {/* Disruption subtitle */}
      {disruptionCount > 0 && (
        <p className="text-amber-500/60 text-xs mb-3 pl-3.5">
          {disruptionCount === 1
            ? `1 disruption · tap a class to see details`
            : `${disruptionCount} disruptions · tap a class to see details`}
        </p>
      )}
      {disruptionCount === 0 && <div className="mb-3" />}

      {timelineItems.length > 0 ? (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {timelineItems.map((item) => {
              if (item.kind === 'event') {
                return (
                  <EventChip
                    key={`event-${item.event.id}`}
                    event={item.event}
                    isActive={selectedEventId === item.event.id}
                    onClick={() => handleEventClick(item.event.id)}
                    onDismiss={() => dismissEvent.mutate(item.event.id)}
                  />
                );
              }
              const { period, index } = item;
              const groupAbsences = peekOffset === 0
                ? absences.filter((a) => a.group_name === period.group)
                : [];
              const groupDisruptions = displayDisruptions.filter((d) =>
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
              disruptions={displayDisruptions.filter((d) =>
                groupIsAffected(d, selectedPeriod.group)
              )}
              onClose={() => setSelectedGroup(null)}
              autoOpenPlanNonce={
                openLessonPlan?.group === selectedPeriod.group ? openLessonPlan?.nonce : undefined
              }
            />
          )}

          {selectedEvent && eventsToday.some((e) => e.id === selectedEvent.id) && (
            <EventCard
              event={selectedEvent}
              onClose={() => setSelectedEventId(null)}
              onChat={() => setChatEvent(selectedEvent)}
              onVoice={() => onVoiceAboutEvent?.(eventFocusSummary(selectedEvent))}
            />
          )}
        </>
      ) : (
        <p className="text-stone-700 text-sm">
          {isWeekend && peekOffset === 0 ? 'Enjoy the rest.' : 'No classes scheduled.'}
        </p>
      )}

      {/* Coming up — quiet heads-up for the next couple of days. Only rendered
          when there's something relevant; absent (no empty state) otherwise. It
          graduates onto the timeline above once its day becomes today. */}
      {peekOffset === 0 && upcomingEvents.length > 0 && (
        <div className="mt-6">
          <h3 className="text-stone-600 text-xs font-semibold tracking-widest uppercase mb-2">
            Coming up
          </h3>
          <div className="space-y-1">
            {upcomingEvents.map((event) => (
              <div key={event.id} className="relative">
                <button
                  onClick={() => handleEventClick(event.id)}
                  className="w-full text-left flex items-center gap-2 pr-6 py-1.5 transition-colors group"
                >
                  <span className="text-amber-500/50 flex-shrink-0"><CalendarIcon /></span>
                  <span className="text-stone-500 text-xs flex-shrink-0">
                    {upcomingDateLabel(event.date, today)}{event.start_time ? ` ${event.start_time}` : ''}
                  </span>
                  <span className="text-stone-300 group-hover:text-stone-100 text-xs truncate transition-colors">
                    · {event.title}
                  </span>
                  {event.location && (
                    <span className="text-stone-600 text-xs truncate">— {event.location}</span>
                  )}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); dismissEvent.mutate(event.id); }}
                  aria-label={`Dismiss ${event.title}`}
                  className="absolute top-1.5 right-1 text-stone-700 hover:text-stone-400 text-xs leading-none transition-colors"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          {selectedEvent && upcomingEvents.some((e) => e.id === selectedEvent.id) && (
            <EventCard
              event={selectedEvent}
              onClose={() => setSelectedEventId(null)}
              onChat={() => setChatEvent(selectedEvent)}
              onVoice={() => onVoiceAboutEvent?.(eventFocusSummary(selectedEvent))}
            />
          )}
        </div>
      )}

      <EventChatDrawer event={chatEvent} onClose={() => setChatEvent(null)} />
    </div>
  );
}
