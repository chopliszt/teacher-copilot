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
  const [ignoreDraft, setIgnoreDraft] = useState('');
  const [personalDraft, setPersonalDraft] = useState('');
  const [savedFlash, setSavedFlash] = useState(false);

  const { data } = usePreferences();
  const save = useSavePreferences();

  useEffect(() => {
    if (open) {
      setIgnoreDraft(data?.ignore_rules ?? '');
      setPersonalDraft(data?.personal_context ?? '');
    }
  }, [open, data?.ignore_rules, data?.personal_context]);

  function handleSave() {
    save.mutate(
      { ignore_rules: ignoreDraft, personal_context: personalDraft },
      {
        onSuccess: () => {
          setSavedFlash(true);
          setTimeout(() => setSavedFlash(false), 1500);
          setTimeout(() => setOpen(false), 600);
        },
      },
    );
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
          className="fixed inset-0 z-50 bg-stone-950/80 backdrop-blur-sm flex items-start justify-center pt-12 px-4 overflow-y-auto"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-5 my-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold tracking-widest uppercase text-stone-400">
                Settings
              </h2>
              <button
                onClick={() => setOpen(false)}
                className="text-stone-600 hover:text-stone-300 text-xs"
              >
                close
              </button>
            </div>

            <section className="space-y-2">
              <h3 className="text-stone-300 text-xs font-semibold">
                About me / How I work
              </h3>
              <p className="text-stone-500 text-xs leading-relaxed">
                Persistent context Marimba uses when chatting and drafting
                content (slides, handouts, prompts, emails). Example:
                <br />
                <span className="text-stone-600 italic">
                  "I prefer minimalistic slides. Handouts should be
                  ADHD-friendly with short instructions and one task per
                  section. When you generate prompts for ClaudeAI, keep them
                  short and direct."
                </span>
              </p>
              <textarea
                value={personalDraft}
                onChange={(e) => setPersonalDraft(e.target.value)}
                placeholder="How do you like to work? What's your style?"
                rows={6}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
              />
            </section>

            <section className="space-y-2">
              <h3 className="text-stone-300 text-xs font-semibold">
                Ignore rules
              </h3>
              <p className="text-stone-500 text-xs leading-relaxed">
                What Marimba should treat as low value (filters emails and
                Top 3 candidates). Example:
                <br />
                <span className="text-stone-600 italic">
                  "ignore uniform checks unless a parent complains; skip grade
                  11 and 12 emails with no direct ask."
                </span>
              </p>
              <textarea
                value={ignoreDraft}
                onChange={(e) => setIgnoreDraft(e.target.value)}
                placeholder="One rule per line, or one paragraph."
                rows={5}
                className="w-full bg-stone-950 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-300 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
              />
            </section>

            <div className="flex items-center justify-between">
              <span className="text-xs text-stone-600">
                {savedFlash
                  ? 'Saved'
                  : save.isError
                  ? 'Failed to save — try again'
                  : ' '}
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
