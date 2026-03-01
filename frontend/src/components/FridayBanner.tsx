import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadWeeklySchedule } from '../lib/api/client';

function isFriday(): boolean {
  return new Date().getDay() === 5;
}

interface FridayBannerProps {
  hasWeeklyData: boolean;
}

export function FridayBanner({ hasWeeklyData }: FridayBannerProps) {
  const showBanner = isFriday() || !hasWeeklyData;
  const [pasteOpen, setPasteOpen] = useState(false);
  const [text, setText] = useState('');
  const [done, setDone] = useState(false);
  const queryClient = useQueryClient();

  const upload = useMutation({
    mutationFn: (content: string) => uploadWeeklySchedule(content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['weekly-schedule'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
      setDone(true);
      setPasteOpen(false);
      setText('');
      setTimeout(() => setDone(false), 4000);
    },
  });

  if (!showBanner) return null;

  return (
    <div className="mb-6">
      <div className="bg-stone-900/70 border border-stone-800 rounded-2xl px-4 py-3 space-y-3">
        {/* Header row */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-base">📋</span>
            <div>
              <p className="text-stone-300 text-sm font-medium">
                {done ? 'Weekly announcements updated ✓' : 'Weekly announcements'}
              </p>
              {!done && (
                <p className="text-stone-600 text-xs mt-0.5">
                  {isFriday() && !hasWeeklyData
                    ? "Two emails arrive today — paste them here when you get them."
                    : isFriday()
                    ? "It's Friday — update this week's announcements if they've changed."
                    : "No announcements loaded yet for this week."}
                </p>
              )}
            </div>
          </div>
          {!done && (
            <button
              onClick={() => setPasteOpen((o) => !o)}
              className="flex-shrink-0 text-xs text-stone-500 hover:text-stone-300 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-colors"
            >
              {pasteOpen ? 'Cancel' : 'Paste →'}
            </button>
          )}
        </div>

        {/* Inline paste panel */}
        {pasteOpen && (
          <div className="space-y-2 pt-1">
            <textarea
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the full text of the weekly announcement emails here…"
              rows={6}
              className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
            />
            <button
              onClick={() => upload.mutate(text)}
              disabled={!text.trim() || upload.isPending}
              className="w-full py-2.5 rounded-xl bg-stone-700 hover:bg-stone-600 disabled:opacity-40 disabled:cursor-not-allowed text-stone-200 text-sm font-medium transition-all"
            >
              {upload.isPending ? 'Processing…' : 'Process announcements'}
            </button>
            {upload.isError && (
              <p className="text-red-400 text-xs">
                Something went wrong — check that the backend is running.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
