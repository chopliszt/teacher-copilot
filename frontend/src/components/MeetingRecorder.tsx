import { useEffect, useRef, useState } from 'react';
import { useMeetingRecorder } from '../lib/hooks/useMeetingRecorder';

interface MeetingRecorderProps {
  /** When this flips to true, immediately start recording (Marimba voice trigger). */
  triggerRecord?: boolean;
  /** Called after triggerRecord is consumed so App.tsx can reset the flag. */
  onTriggerConsumed?: () => void;
  /** Called when recording starts — lets the parent put Marimba in 'listening' state. */
  onRecordingStart?: () => void;
  /** Called when processing completes (success or error). */
  onProcessingDone?: (message: string) => void;
}

function formatSeconds(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// ── SVG icons ─────────────────────────────────────────────────────────────────

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" x2="12" y1="3" y2="15" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MeetingRecorder({
  triggerRecord,
  onTriggerConsumed,
  onRecordingStart,
  onProcessingDone,
}: MeetingRecorderProps) {
  const {
    state,
    recordingSeconds,
    draft,
    errorMessage,
    savedFilename,
    startRecording,
    stopAndProcess,
    discardRecording,
    uploadFile,
    proceedToCompose,
    sendEmail,
    redownloadSavedRecording,
    reset,
  } = useMeetingRecorder();

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Editable email fields — pre-filled from draft, user can modify before sending
  const [emailTo, setEmailTo] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');

  // Populate email fields when the draft arrives
  useEffect(() => {
    if (draft && state === 'composing') {
      if (!emailSubject) setEmailSubject(draft.suggested_subject);
      if (!emailBody) setEmailBody(draft.email_body);
    }
  }, [draft, state, emailSubject, emailBody]);

  // When moving to composing for the first time, seed the fields
  const handleProceedToCompose = () => {
    if (draft) {
      setEmailSubject(draft.suggested_subject);
      setEmailBody(draft.email_body);
    }
    proceedToCompose();
  };

  // Marimba voice trigger
  useEffect(() => {
    if (triggerRecord && state === 'idle') {
      startRecording().then(() => onRecordingStart?.());
      onTriggerConsumed?.();
    }
  }, [triggerRecord, state, startRecording, onRecordingStart, onTriggerConsumed]);

  // Drive Marimba's speech bubble at key moments in the meeting flow
  useEffect(() => {
    if (state === 'processing') {
      onProcessingDone?.('Guardando la grabación, profe. Te aviso cuando esté lista.');
    } else if (state === 'review') {
      onProcessingDone?.('El resumen está listo, profe. ¿Lo enviamos?');
    } else if (state === 'done') {
      onProcessingDone?.('Listo, profe. El correo fue enviado.');
    }
  }, [state, onProcessingDone]);

  // Auto-reset after "done" state
  useEffect(() => {
    if (state === 'done') {
      const timer = setTimeout(reset, 4000);
      return () => clearTimeout(timer);
    }
  }, [state, reset]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadFile(file);
      // Reset the input so the same file can be re-selected if needed
      e.target.value = '';
    }
  };

  const handleSend = () => {
    if (!emailTo.trim() || !emailSubject.trim()) return;
    sendEmail(emailTo.trim(), emailSubject.trim(), emailBody);
  };

  const handleReset = () => {
    setEmailTo('');
    setEmailSubject('');
    setEmailBody('');
    reset();
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <section className="mt-8">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-1.5 h-1.5 rounded-full transition-colors ${
          state === 'recording' ? 'bg-red-400 animate-pulse' : 'bg-stone-600'
        }`} />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          Meeting Notes
        </h2>
      </div>

      {/* ── Idle: record + upload buttons ────────────────────────────────── */}
      {state === 'idle' && (
        <div className="flex gap-2">
          <button
            onClick={() => startRecording().then(() => onRecordingStart?.())}
            className="flex items-center gap-1.5 text-stone-500 hover:text-stone-300 text-xs border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-all active:scale-95 cursor-pointer"
          >
            <MicIcon />
            Record
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 text-stone-500 hover:text-stone-300 text-xs border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-all active:scale-95 cursor-pointer"
          >
            <UploadIcon />
            Upload file
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,video/mp4,video/webm"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      )}

      {/* ── Recording ───────────────────────────────────────────────────── */}
      {state === 'recording' && (
        <div className="bg-stone-900 border border-red-500/20 rounded-2xl px-4 py-3 flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse flex-shrink-0" />
          <span className="text-red-400 text-xs font-mono tabular-nums flex-1">
            {formatSeconds(recordingSeconds)}
          </span>
          <button
            onClick={stopAndProcess}
            className="flex items-center gap-1.5 text-stone-300 hover:text-stone-100 text-xs border border-stone-700 hover:border-stone-600 px-3 py-1.5 rounded-lg transition-all active:scale-95 cursor-pointer"
          >
            <StopIcon />
            Stop &amp; process
          </button>
          <button
            onClick={discardRecording}
            className="text-stone-700 hover:text-stone-500 text-xs transition-colors cursor-pointer"
            aria-label="Discard recording"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Processing ──────────────────────────────────────────────────── */}
      {state === 'processing' && (
        <div className="bg-stone-900 border border-stone-800 rounded-2xl px-4 py-3 space-y-1.5">
          <div className="flex items-center gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            <span className="text-stone-500 text-sm">Transcribing meeting…</span>
          </div>
          {savedFilename && (
            <p className="text-stone-700 text-xs pl-4">
              Saved to Downloads: <span className="text-stone-600 font-mono">{savedFilename}</span>
            </p>
          )}
        </div>
      )}

      {/* ── Review: summary + action items ──────────────────────────────── */}
      {state === 'review' && draft && (
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-4">
          {/* Summary */}
          <div>
            <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase mb-2">Summary</p>
            <p className="text-stone-300 text-sm leading-relaxed">{draft.summary}</p>
          </div>

          {/* Action items */}
          {draft.action_items.length > 0 && (
            <div>
              <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase mb-2">Action items</p>
              <ul className="space-y-1">
                {draft.action_items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-amber-500/60 text-xs mt-0.5 flex-shrink-0">·</span>
                    <span className="text-stone-400 text-sm">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1 border-t border-stone-800">
            <button
              onClick={handleProceedToCompose}
              className="flex items-center gap-1.5 text-xs font-medium text-amber-400 hover:text-amber-300 border border-amber-500/20 hover:border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/10 px-3 py-1.5 rounded-lg transition-all active:scale-95 cursor-pointer"
            >
              <MailIcon />
              Send as email
            </button>
            <button
              onClick={handleReset}
              className="text-stone-700 hover:text-stone-500 text-xs px-3 py-1.5 transition-colors cursor-pointer"
            >
              Discard
            </button>
          </div>
        </div>
      )}

      {/* ── Composing: email form ────────────────────────────────────────── */}
      {state === 'composing' && draft && (
        <div className="bg-stone-900 border border-stone-800 rounded-2xl p-5 space-y-3">
          {/* To */}
          <div>
            <label className="text-stone-600 text-xs font-semibold tracking-widest uppercase block mb-1.5">To</label>
            <input
              autoFocus
              type="email"
              value={emailTo}
              onChange={(e) => setEmailTo(e.target.value)}
              placeholder="recipient@school.edu"
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-stone-200 text-sm placeholder-stone-700 focus:outline-none focus:border-stone-600 transition-colors"
            />
          </div>

          {/* Subject */}
          <div>
            <label className="text-stone-600 text-xs font-semibold tracking-widest uppercase block mb-1.5">Subject</label>
            <input
              type="text"
              value={emailSubject}
              onChange={(e) => setEmailSubject(e.target.value)}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-stone-200 text-sm placeholder-stone-700 focus:outline-none focus:border-stone-600 transition-colors"
            />
          </div>

          {/* Body */}
          <div>
            <label className="text-stone-600 text-xs font-semibold tracking-widest uppercase block mb-1.5">Body</label>
            <textarea
              value={emailBody}
              onChange={(e) => setEmailBody(e.target.value)}
              rows={8}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-stone-300 text-sm placeholder-stone-700 focus:outline-none focus:border-stone-600 transition-colors resize-y"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-1 border-t border-stone-800">
            <button
              onClick={handleSend}
              disabled={!emailTo.trim() || !emailSubject.trim()}
              className="flex items-center gap-1.5 flex-1 justify-center py-2 text-xs font-medium text-stone-200 bg-stone-700 hover:bg-stone-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-all active:scale-95 cursor-pointer"
            >
              <MailIcon />
              Send email
            </button>
            <button
              onClick={() => proceedToCompose()}
              className="flex items-center gap-1 text-stone-600 hover:text-stone-400 text-xs px-3 py-2 border border-stone-800 hover:border-stone-700 rounded-lg transition-all cursor-pointer"
            >
              <ChevronLeftIcon />
              Back
            </button>
          </div>
        </div>
      )}

      {/* ── Sending ─────────────────────────────────────────────────────── */}
      {state === 'sending' && (
        <div className="bg-stone-900 border border-stone-800 rounded-2xl px-4 py-3 flex items-center gap-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-stone-500 text-sm">Sending email…</span>
        </div>
      )}

      {/* ── Done ────────────────────────────────────────────────────────── */}
      {state === 'done' && (
        <div className="bg-stone-900 border border-stone-800 rounded-2xl px-4 py-3 flex items-center gap-2.5">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-amber-400">
            <path d="M20 6 9 17l-5-5" />
          </svg>
          <span className="text-stone-400 text-sm">Email sent</span>
        </div>
      )}

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {state === 'error' && (
        <div className="bg-stone-900 border border-red-500/20 rounded-2xl px-4 py-3 space-y-3">
          <p className="text-red-400 text-sm">{errorMessage}</p>
          {savedFilename && (
            <div className="bg-stone-950/60 border border-stone-800 rounded-xl px-3 py-2.5 space-y-1">
              <p className="text-stone-500 text-xs">
                Recording saved as <span className="text-stone-400 font-mono">{savedFilename}</span> in your Downloads folder.
              </p>
              <p className="text-stone-600 text-xs">
                You can re-upload it via the Upload button once the issue is resolved.
              </p>
              <button
                onClick={redownloadSavedRecording}
                className="text-amber-500/70 hover:text-amber-400 text-xs transition-colors cursor-pointer underline underline-offset-2"
              >
                Download again
              </button>
            </div>
          )}
          <button
            onClick={handleReset}
            className="text-stone-600 hover:text-stone-400 text-xs transition-colors cursor-pointer"
          >
            Try again
          </button>
        </div>
      )}
    </section>
  );
}
