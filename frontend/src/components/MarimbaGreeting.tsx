import { getTimeOfDayGreeting, formatTodayLabel } from '../lib/utils/dateUtils';

const MARIMBA_MESSAGE_BY_PRIORITY_COUNT: Record<number, string> = {
  0: "All clear — you're ahead of the game today.",
  1: "One thing needs your attention. Let's make it happen.",
  2: "Two priorities queued up. You've got this.",
  3: "Here's what matters most right now.",
};

interface MarimbaGreetingProps {
  priorityCount: number;
}

export function MarimbaGreeting({ priorityCount }: MarimbaGreetingProps) {
  const greeting = getTimeOfDayGreeting();
  const todayLabel = formatTodayLabel();
  const marimbaSays =
    MARIMBA_MESSAGE_BY_PRIORITY_COUNT[priorityCount] ??
    MARIMBA_MESSAGE_BY_PRIORITY_COUNT[3];

  return (
    <header className="mb-10">
      <p className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
        {greeting} · {todayLabel}
      </p>
      <h1 className="text-stone-50 text-xl font-bold mt-1">Marimba</h1>
      <p className="text-stone-400 mt-1 text-sm leading-relaxed">
        {marimbaSays}
      </p>
    </header>
  );
}
