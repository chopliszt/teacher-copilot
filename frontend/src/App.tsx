import { useCallback, useState } from 'react';
import { usePriorities } from './lib/hooks/usePriorities';
import { useWeeklySchedule } from './lib/hooks/useWeeklySchedule';
import { useVoice } from './lib/hooks/useVoice';
import { MarimbaGreeting } from './components/MarimbaGreeting';
import { MarimbaWidget } from './components/MarimbaWidget';
import { PriorityList } from './components/PriorityList';
import { TodaySchedule } from './components/TodaySchedule';
import { InboxTray } from './components/InboxTray';
import { UserTaskSection } from './components/UserTaskSection';
import { FridayBanner } from './components/FridayBanner';
import type { VoiceAction } from './lib/api/client';

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-stone-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-amber-500/20 border-t-amber-400 animate-spin" />
        <p className="text-stone-600 text-sm">Marimba is thinking…</p>
      </div>
    </div>
  );
}

interface ErrorScreenProps {
  message: string;
}

function ErrorScreen({ message }: ErrorScreenProps) {
  return (
    <div className="min-h-screen bg-stone-950 flex items-center justify-center p-6">
      <div className="max-w-sm w-full bg-stone-900 border border-red-500/20 rounded-2xl p-6">
        <div className="text-3xl mb-3">😔</div>
        <h2 className="text-stone-100 font-semibold mb-1">Marimba can't connect</h2>
        <p className="text-stone-400 text-sm mb-4">
          Could not reach the backend. Make sure it's running at{' '}
          <code className="text-amber-400 text-xs">localhost:8000</code>.
        </p>
        <pre className="bg-stone-950 text-red-400 text-xs p-3 rounded-lg overflow-auto whitespace-pre-wrap">
          {message}
        </pre>
      </div>
    </div>
  );
}

export default function App() {
  const { data, isLoading, isError, error } = usePriorities();
  const { data: weeklySchedule } = useWeeklySchedule();

  // Voice-triggered class briefing state
  const [voiceOpenGroup, setVoiceOpenGroup] = useState<string | null>(null);
  const [voiceOpenPriority, setVoiceOpenPriority] = useState<string | null>(null);
  // Counter that increments each time "close_all" is received — children watch this
  const [closeAllCounter, setCloseAllCounter] = useState(0);

  const handleVoiceAction = useCallback((action: VoiceAction) => {
    if (action.type === 'open_class' && action.group) {
      setVoiceOpenGroup(action.group);
      // Scroll the schedule section into view so the briefing panel is visible
      setTimeout(() => {
        document.getElementById('today-schedule')?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else if (action.type === 'open_priority' && action.id) {
      setVoiceOpenPriority(action.id);
      setTimeout(() => {
        document.getElementById('priorities-section')?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else if (action.type === 'close_all') {
      setVoiceOpenGroup(null);
      setVoiceOpenPriority(null);
      setCloseAllCounter((prev) => prev + 1);
    }
    // add_task: backend already saved it; useVoice invalidates queries automatically
  }, []);

  const { marimbaState, toggleListening, isSupported, lastResponse } = useVoice({
    onAction: handleVoiceAction,
  });

  if (isLoading) return <LoadingScreen />;
  if (isError) return <ErrorScreen message={error?.message ?? 'Unknown error'} />;

  const priorities = data?.priorities ?? [];
  const hasWeeklyData = !!(weeklySchedule?.week_label);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-50">
      <main className="max-w-4xl mx-auto px-4 py-10 sm:px-6 lg:px-8">
        <MarimbaGreeting priorityCount={priorities.length} />
        <div id="today-schedule">
          <TodaySchedule openGroup={voiceOpenGroup} closeAllCounter={closeAllCounter} />
        </div>
        <FridayBanner hasWeeklyData={hasWeeklyData} />
        <div id="priorities-section">
          <PriorityList priorities={priorities} openPriorityId={voiceOpenPriority} closeAllCounter={closeAllCounter} />
        </div>
        <UserTaskSection />
        <InboxTray />
      </main>
      <MarimbaWidget
        state={marimbaState}
        isSupported={isSupported}
        onMicClick={toggleListening}
        lastResponse={lastResponse}
      />
    </div>
  );
}
