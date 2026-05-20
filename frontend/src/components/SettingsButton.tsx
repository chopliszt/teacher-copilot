import { useEffect, useState } from 'react';
import { usePreferences, useSavePreferences } from '../lib/hooks/usePreferences';

function GearIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export function SettingsButton() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [savedFlash, setSavedFlash] = useState(false);

  const { data } = usePreferences();
  const save = useSavePreferences();

  useEffect(() => {
    if (open) setDraft(data?.ignore_rules ?? '');
  }, [open, data?.ignore_rules]);

  function handleSave() {
    save.mutate(draft, {
      onSuccess: () => {
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 1500);
        setTimeout(() => setOpen(false), 600);
      },
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Settings"
        className="fixed top-4 right-4 z-40 w-9 h-9 rounded-full bg-stone-900/70 border border-stone-800 text-stone-500 hover:text-stone-300 hover:border-stone-700 flex items-center justify-center transition-all duration-300 active:scale-95"
      >
        <GearIcon />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-stone-950/80 backdrop-blur-sm flex items-start justify-center pt-20 px-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold tracking-widest uppercase text-stone-400">
                Ignore rules
              </h2>
              <button
                onClick={() => setOpen(false)}
                className="text-stone-600 hover:text-stone-300 text-xs"
              >
                close
              </button>
            </div>
            <p className="text-stone-500 text-xs leading-relaxed">
              Free-form rules describing what Marimba should treat as low value
              (incoming emails and Top 3 candidates). Example:
              <br />
              <span className="text-stone-600 italic">
                "ignore uniform checks unless a parent complains; skip grade
                11–12 emails with no direct ask; treat 'chairs at end of day'
                as routine."
              </span>
            </p>
            <textarea
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="One rule per line, or one paragraph. Whatever feels natural."
              rows={8}
              className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-600">
                {savedFlash
                  ? 'Saved ✓'
                  : save.isError
                  ? 'Failed to save — try again'
                  : ' '}
              </span>
              <button
                onClick={handleSave}
                disabled={save.isPending}
                className="text-xs px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-300 hover:bg-amber-500/30 disabled:opacity-40 transition-all duration-300 active:scale-95"
              >
                {save.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
