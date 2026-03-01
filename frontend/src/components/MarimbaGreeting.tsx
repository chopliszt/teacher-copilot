import { useEffect, useState } from 'react';
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
  const [theme, setTheme] = useState('stone');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);
  const greeting = getTimeOfDayGreeting();
  const todayLabel = formatTodayLabel();
  const marimbaSays =
    MARIMBA_MESSAGE_BY_PRIORITY_COUNT[priorityCount] ??
    MARIMBA_MESSAGE_BY_PRIORITY_COUNT[3];

  return (
    <header className="mb-10 flex justify-between items-start">
      <div>
        <p className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          {greeting} · {todayLabel}
        </p>
        <h1 className="text-stone-50 text-xl font-bold mt-1">Marimba</h1>
        <p className="text-stone-400 mt-1 text-sm leading-relaxed">
          {marimbaSays}
        </p>
      </div>

      <select 
        value={theme}
        onChange={(e) => setTheme(e.target.value)}
        className="bg-stone-900 border border-stone-800 text-stone-400 text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-amber-500/50"
      >
        <option value="stone">Original (Stone/Amber)</option>
        <option value="ocean">Ocean (Slate/Cyan)</option>
        <option value="forest">Forest (Zinc/Emerald)</option>
      </select>
    </header>
  );
}
