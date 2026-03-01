import { usePriorities } from './lib/hooks/usePriorities';
import { MarimbaGreeting } from './components/MarimbaGreeting';
import { MarimbaWidget } from './components/MarimbaWidget';
import { PriorityList } from './components/PriorityList';
import { TodaySchedule } from './components/TodaySchedule';

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

  if (isLoading) return <LoadingScreen />;
  if (isError) return <ErrorScreen message={error?.message ?? 'Unknown error'} />;

  const priorities = data?.priorities ?? [];

  return (
    <div className="min-h-screen bg-stone-950 text-stone-50">
      <main className="max-w-4xl mx-auto px-4 py-10 sm:px-6 lg:px-8">
        <MarimbaGreeting priorityCount={priorities.length} />
        <TodaySchedule />
        <PriorityList priorities={priorities} />
      </main>
      <MarimbaWidget />
    </div>
  );
}
