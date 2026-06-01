import { useEffect, useId, useRef, useState } from 'react';
import {
  composeEmail,
  fetchEmailRecipients,
  saveEmailComposeAsDraft,
  type EmailRecipient,
} from '../lib/api/client';
import { playCannedAudio } from '../lib/cannedAudio';
import type { ParsedEmailArtifact } from '../lib/parseEmailArtifact';

interface EmailComposerProps {
  initial: ParsedEmailArtifact;
}

/**
 * Inline email composer rendered inside the chat thread whenever Marimba
 * emits a fenced `email` block. Fields are pre-filled with what she drafted,
 * and the teacher edits + sends in place. Mirrors the meeting-recorder
 * composer style so the UX feels consistent across the app.
 *
 * Recipient autocomplete is powered by a native <datalist> backed by
 * /api/email-recipients (past sends + inbox senders, ranked by use_count).
 * Attachments are real File objects sent as multipart/form-data.
 *
 * After a successful send the whole composer collapses to a single-line
 * confirmation chip — the editable form gets out of the way and the chat
 * thread stays scannable.
 */
export function EmailComposer({ initial }: EmailComposerProps) {
  const [to, setTo] = useState(initial.to);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const [cc, setCc] = useState('');
  // CC row stays hidden until the teacher explicitly adds one — avoids
  // visual noise on the common no-CC case while keeping the option a
  // single click away.
  const [ccVisible, setCcVisible] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [savedAsDraft, setSavedAsDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recipients, setRecipients] = useState<EmailRecipient[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const datalistId = useId();
  const ccDatalistId = useId();

  useEffect(() => {
    fetchEmailRecipients().then(setRecipients).catch(() => {});
  }, []);

  function addFiles(picked: FileList | null) {
    if (!picked) return;
    const next = [...files];
    for (const f of Array.from(picked)) {
      if (!next.some((x) => x.name === f.name && x.size === f.size)) {
        next.push(f);
      }
    }
    setFiles(next);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function removeFile(idx: number) {
    setFiles(files.filter((_, i) => i !== idx));
  }

  async function handleSaveDraft() {
    if (savingDraft || savedAsDraft) return;
    if (!body.trim()) {
      setError('Body is required to save a draft.');
      return;
    }
    setSavingDraft(true);
    setError(null);
    try {
      const toClean = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to.trim()) ? to.trim() : undefined;
      await saveEmailComposeAsDraft({ to: toClean, subject, body, cc: cc.trim() || undefined });
      setSavedAsDraft(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Draft save failed. Check the backend logs.');
    } finally {
      setSavingDraft(false);
    }
  }

  async function handleSend() {
    if (sending || sent) return;
    if (!to.trim() || !body.trim()) {
      setError('Recipient and body are required.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      await composeEmail({ to, subject, body, cc: cc.trim() || undefined, attachments: files });
      setSent(true);
      playCannedAudio('email_sent.mp3');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Send failed. Check the backend logs.');
    } finally {
      setSending(false);
    }
  }

  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  const sizeOver = totalBytes > 20 * 1024 * 1024;

  // ── Sent / Draft saved: collapse to a single confirmation chip ─────────────
  if (sent || savedAsDraft) {
    const recipientPreview = to
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const firstRecipient = recipientPreview[0] ?? '';
    const extras = recipientPreview.length > 1 ? ` +${recipientPreview.length - 1}` : '';
    return (
      <div className="my-3 max-w-full rounded-xl border border-amber-500/30 bg-stone-900 px-4 py-3 flex items-center gap-3">
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-amber-400 flex-shrink-0"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
        <div className="min-w-0 flex-1">
          <p className="text-stone-200 text-sm leading-tight">
            {savedAsDraft ? 'Draft saved to Gmail' : 'Email sent'}
          </p>
          <p className="text-stone-600 text-xs truncate mt-0.5">
            {firstRecipient ? `To ${firstRecipient}${extras}` : 'No recipient set'}
            {files.length > 0 && (
              <span className="text-stone-700">
                {' · '}
                {files.length} attachment{files.length === 1 ? '' : 's'}
              </span>
            )}
          </p>
        </div>
      </div>
    );
  }

  // ── Draft: editable composer ────────────────────────────────────────────────
  const recipientCount = to
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean).length;
  const recipientLabel =
    recipientCount === 0
      ? 'no recipients yet'
      : `${recipientCount} recipient${recipientCount === 1 ? '' : 's'}`;
  const attachmentLabel =
    files.length === 0
      ? 'no attachments'
      : `${files.length} attachment${files.length === 1 ? '' : 's'}`;

  return (
    <div className="my-3 max-w-full rounded-xl border border-amber-500/25 bg-stone-950 overflow-hidden">
      {/* Header — title + at-a-glance summary so the teacher can verify */}
      {/* recipient/attachment counts before scrolling the body. */}
      <div className="px-4 py-2 bg-amber-500/5 border-b border-amber-500/15 flex items-center gap-2 flex-wrap">
        <span className="text-amber-400/80 text-[0.7rem] font-semibold tracking-widest uppercase">
          Email draft — review and send
        </span>
        <span className="text-stone-600 text-[0.7rem]">
          · {recipientLabel} · {attachmentLabel}
        </span>
      </div>

      <div className="p-4 space-y-3">
        {/* To */}
        <label className="block min-w-0">
          <span className="text-[0.65rem] uppercase tracking-widest text-stone-600 font-semibold flex items-center justify-between">
            <span>To</span>
            {!ccVisible && (
              <button
                onClick={() => setCcVisible(true)}
                className="text-stone-600 hover:text-stone-400 text-[0.65rem] normal-case tracking-normal font-normal"
              >
                + Cc
              </button>
            )}
          </span>
          <input
            list={datalistId}
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="recipient@example.com (comma-separate for multiple)"
            className="block w-full max-w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-1.5 text-stone-200 text-xs mt-1 focus:outline-none focus:border-stone-600"
          />
          <datalist id={datalistId}>
            {recipients.map((r) => (
              <option key={r.email} value={r.email}>
                {r.label ?? ''}
              </option>
            ))}
          </datalist>
        </label>

        {/* Cc — hidden by default; appears on demand to keep the form quiet
            for the common no-CC case. Once visible, it stays — clearing the
            field collapses it back via the × control. */}
        {ccVisible && (
          <label className="block min-w-0">
            <span className="text-[0.65rem] uppercase tracking-widest text-stone-600 font-semibold flex items-center justify-between">
              <span>Cc</span>
              <button
                onClick={() => {
                  setCc('');
                  setCcVisible(false);
                }}
                className="text-stone-600 hover:text-amber-400 text-[0.65rem] normal-case tracking-normal font-normal"
              >
                remove
              </button>
            </span>
            <input
              list={ccDatalistId}
              value={cc}
              onChange={(e) => setCc(e.target.value)}
              placeholder="cc@example.com (comma-separate for multiple)"
              className="block w-full max-w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-1.5 text-stone-200 text-xs mt-1 focus:outline-none focus:border-stone-600"
            />
            <datalist id={ccDatalistId}>
              {recipients.map((r) => (
                <option key={r.email} value={r.email}>
                  {r.label ?? ''}
                </option>
              ))}
            </datalist>
          </label>
        )}

        {/* Subject */}
        <label className="block min-w-0">
          <span className="text-[0.65rem] uppercase tracking-widest text-stone-600 font-semibold">
            Subject
          </span>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="block w-full max-w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-1.5 text-stone-200 text-xs mt-1 focus:outline-none focus:border-stone-600"
          />
        </label>

        {/* Body — bumped to text-sm since this is the most-read field */}
        <label className="block min-w-0">
          <span className="text-[0.65rem] uppercase tracking-widest text-stone-600 font-semibold">
            Body
          </span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            className="block w-full max-w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-stone-200 text-sm mt-1 focus:outline-none focus:border-stone-600 resize-y"
          />
        </label>

        {/* Attachments */}
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[0.65rem] uppercase tracking-widest text-stone-600 font-semibold">
              Attachments
            </span>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-[0.7rem] text-stone-500 hover:text-stone-300 border border-stone-800 hover:border-stone-700 rounded-lg px-2 py-0.5 transition-colors"
            >
              + Add file
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={(e) => addFiles(e.target.files)}
            className="hidden"
          />
          {files.length === 0 ? (
            <p className="text-stone-700 text-[0.7rem] italic">No attachments.</p>
          ) : (
            <ul className="space-y-1">
              {files.map((f, i) => (
                <li
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between gap-2 bg-stone-900 border border-stone-800 rounded-lg px-2 py-1 min-w-0"
                >
                  <span className="text-stone-300 text-[0.7rem] truncate min-w-0">
                    {f.name}{' '}
                    <span className="text-stone-600">({formatBytes(f.size)})</span>
                  </span>
                  <button
                    onClick={() => removeFile(i)}
                    aria-label={`Remove ${f.name}`}
                    className="text-stone-600 hover:text-amber-400 text-xs flex-shrink-0"
                  >
                    ✕
                  </button>
                </li>
              ))}
              <li className="text-stone-700 text-[0.65rem] pl-1">
                Total: {formatBytes(totalBytes)} / 20 MB cap
              </li>
            </ul>
          )}
        </div>

        {/* Send-error panel — mirrors the meeting composer so the user never
            loses their draft to a backend hiccup. */}
        {error && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl px-3 py-2.5">
            <p className="text-red-400 text-xs leading-relaxed">{error}</p>
            <p className="text-stone-600 text-xs mt-1">
              Puedes copiar el cuerpo del correo arriba y enviarlo desde Gmail manualmente.
            </p>
          </div>
        )}

        {/* Action row — single source of truth for status + send. */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-stone-800">
          <span className="text-[0.7rem] min-w-0 truncate">
            {sizeOver ? (
              <span className="text-amber-500/80">Attachments exceed 20 MB.</span>
            ) : (
              <span className="text-stone-700">Review carefully before sending.</span>
            )}
          </span>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={handleSaveDraft}
              disabled={savingDraft || sending || !body.trim()}
              className="text-xs text-stone-400 border border-stone-700 hover:border-stone-600 hover:text-stone-200 px-3 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-40"
            >
              {savingDraft ? 'Saving…' : 'Save as draft'}
            </button>
            <button
              onClick={handleSend}
              disabled={sending || sizeOver || !to.trim() || !body.trim()}
              className="text-xs font-semibold text-amber-300 bg-amber-500/20 border border-amber-500/30 hover:bg-amber-500/30 px-3 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-40"
            >
              {sending ? 'Sending…' : 'Send email'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
