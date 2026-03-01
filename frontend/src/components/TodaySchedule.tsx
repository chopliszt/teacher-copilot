import { useSchedule } from '../lib/hooks/useSchedule';
import { type SchedulePeriod } from '../lib/api/client';

interface PeriodChipProps {
  period: SchedulePeriod;
}

function PeriodChip({ period }: PeriodChipProps) {
  return (
    <div className="flex-shrink-0 bg-stone-900 border border-stone-800 rounded-xl px-3 py-2 min-w-[100px]">
      <p className="text-stone-200 text-xs font-semibold">{period.group}</p>
      <p className="text-stone-500 text-xs mt-0.5">{period.time}</p>
      {period.room && (
        <p className="text-stone-700 text-xs">{period.room}</p>
      )}
    </div>
  );
}

export function TodaySchedule() {
  const { data: schedule, isLoading } = useSchedule();

  if (isLoading || !schedule) return null;

  const jsDay = new Date().getDay();
  const isWeekend = jsDay === 0 || jsDay === 6;

  const todayEntry = schedule.classes.find((day) => day.day === schedule.current_day);
  const periodsToday = isWeekend ? [] : (todayEntry?.periods ?? []);

  const dayLabel = isWeekend
    ? 'Weekend'
    : `Day ${schedule.current_day}`;

  const sectionLabel = periodsToday.length > 0
    ? `Today's Classes · ${dayLabel} · ${periodsToday.length} period${periodsToday.length !== 1 ? 's' : ''}`
    : `Today's Classes · ${dayLabel}`;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1.5 h-1.5 rounded-full bg-stone-600" />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          {sectionLabel}
        </h2>
      </div>

      {periodsToday.length > 0 ? (
        <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {periodsToday.map((period, index) => (
            <PeriodChip key={`${period.group}-${index}`} period={period} />
          ))}
        </div>
      ) : (
        <p className="text-stone-700 text-sm">
          {isWeekend ? 'Enjoy the rest.' : 'No classes scheduled today.'}
        </p>
      )}
    </div>
  );
}
