import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  chatWithTask,
  draftEmailReply,
  fetchEmailDetail,
  saveEmailReplyAsDraft,
  sendEmailReply,
  type ChatMessage,
  type PriorityItem,
} from '../lib/api/client';
import { playCannedAudio } from '../lib/cannedAudio';
import { ChatMessageBubble } from './ChatMessageBubble';

interface TaskChatDrawerProps {
  priority: PriorityItem | null;
  onClose: () => void;
  onDone: () => void;
}

interface DraftState {
  to: string;
  subject: string;
  body: string;
  // Addresses that were on the original Cc line. Surfaced as opt-in chips
  // so the teacher can include some/all of them without re-typing.
  originalCc: string[];
}

export function TaskChatDrawer({ priority, onClose, onDone }: TaskChatDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [chatPending, setChatPending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [draftPending, setDraftPending] = useState(false);
  const [sendPending, setSendPending] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sentOK, setSentOK] = useState(false);
  const [savedDraft, setSavedDraft] = useState(false);
  // Addresses currently selected for inclusion as Cc on send. Subset of
  // draft.originalCc. Empty by default = reply-to-sender-only (safer for
  // accidental over-sharing).
  const [ccIncluded, setCcIncluded] = useState<Set<string>>(new Set());
  const [ccExpanded, setCcExpanded] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const isEmail = priority?.source === 'email';

  // Reset everything when the priority changes (or the drawer is reopened on a new task).
  useEffect(() => {
    setMessages([]);
    setInput('');
    setChatPending(false);
    setChatError(null);
    setDraft(null);
    setDraftPending(false);
    setSendPending(false);
    setSendError(null);
    setSentOK(false);
    setCcIncluded(new Set());
    setCcExpanded(false);
  }, [priority?.id]);

  // Auto-scroll the chat thread as new messages arrive.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, draft]);

  // Proactive opener on mount. Two paths:
  //   - Email tasks (source==='email') hit the dedicated draft-reply
  //     endpoint and populate the draft preview block (with CC chips).
  //     Replies need threading, so they can't go through the chat path.
  //   - Other tasks (user_task / meeting / action_item) hit chatWithTask
  //     with messages=[]. Marimba's first reply contains an `email`,
  //     `draft`, `prompt`, or `handout` fence block (per the FIRST-TURN
  //     OPENER section of the system prompt) — or a concrete question
  //     if the task is too vague to draft against.
  useEffect(() => {
    if (!priority) return;
    let cancelled = false;
    (async () => {
      if (isEmail) {
        setDraftPending(true);
        setSendError(null);
        try {
          const result = await draftEmailReply(priority.id, []);
          if (cancelled) return;
          setDraft({
            to: result.to,
            subject: result.subject,
            body: result.body,
            originalCc: result.original_cc,
          });
          setCcIncluded(new Set());
          setCcExpanded(false);
        } catch (err) {
          if (cancelled) return;
          setSendError(
            err instanceof Error
              ? err.message
              : 'No pude generar el borrador automático. Probá "Draft a reply".',
          );
        } finally {
          if (!cancelled) setDraftPending(false);
        }
        return;
      }

      // Non-email task — let Marimba decide whether to draft or ask.
      setChatPending(true);
      setChatError(null);
      try {
        const result = await chatWithTask({
          task_id: priority.id,
          source: priority.source ?? 'unknown',
          title: priority.title,
          messages: [],
        });
        if (cancelled) return;
        setMessages([
          {
            role: 'assistant',
            content: result.reply,
            tool_calls: result.tool_calls,
          },
        ]);
      } catch (err) {
        if (cancelled) return;
        // Non-fatal — chat input is still there for the teacher to drive.
        setChatError(
          err instanceof Error
            ? err.message
            : 'Marimba no respondió a tiempo. Podés escribirle abajo.',
        );
      } finally {
        if (!cancelled) setChatPending(false);
      }
    })();
    return () => { cancelled = true; };
    // priority?.id triggers the effect on task changes. isEmail and the
    // other refs are stable per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priority?.id]);

  // Close on Escape so the keyboard works like a native modal.
  useEffect(() => {
    if (!priority) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [priority, onClose]);

  // Pull the full email body (with lazy backfill on the backend) when the
  // current task is an email. For non-email tasks, this query is disabled.
  const emailQuery = useQuery({
    queryKey: ['email-detail', priority?.id],
    queryFn: () => fetchEmailDetail(priority!.id),
    enabled: !!priority && isEmail,
    staleTime: 5 * 60_000,
  });

  if (!priority) return null;

  async function handleSend() {
    if (!priority) return;
    const text = input.trim();
    if (!text || chatPending) return;

    const next: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setChatPending(true);
    setChatError(null);

    try {
      const result = await chatWithTask({
        task_id: priority.id,
        source: priority.source ?? 'unknown',
        title: priority.title,
        messages: next.map((m) => ({ role: m.role, content: m.content })),
      });
      setMessages([
        ...next,
        {
          role: 'assistant',
          content: result.reply,
          tool_calls: result.tool_calls,
        },
      ]);
    } catch (err) {
      setChatError(
        err instanceof Error
          ? err.message
          : 'Could not reach the assistant. Try again in a moment.',
      );
      // Rollback the optimistic user message so the user can retry without
      // duplicating it.
      setMessages(messages);
      setInput(text);
    } finally {
      setChatPending(false);
    }
  }

  async function handleDraftReply() {
    if (!priority || draftPending) return;
    setDraftPending(true);
    setSendError(null);
    try {
      const result = await draftEmailReply(priority.id, messages);
      setDraft({
        to: result.to,
        subject: result.subject,
        body: result.body,
        originalCc: result.original_cc,
      });
      // Reset CC state for the new draft — start with no one included so
      // "reply" defaults to the sender only. Teacher opts in via chips.
      setCcIncluded(new Set());
      setCcExpanded(false);
    } catch (err) {
      setSendError(
        err instanceof Error
          ? err.message
          : 'Could not draft a reply. Try again.',
      );
    } finally {
      setDraftPending(false);
    }
  }

  async function handleSendReply() {
    if (!priority || !draft || sendPending) return;
    setSendPending(true);
    setSendError(null);
    try {
      // Only include CC when the teacher explicitly opted into addresses.
      const ccString = ccIncluded.size > 0
        ? Array.from(ccIncluded).join(', ')
        : undefined;
      await sendEmailReply(priority.id, {
        to: draft.to,
        subject: draft.subject,
        body: draft.body,
        cc: ccString,
      });
      setSentOK(true);
      playCannedAudio('email_sent.mp3');
      // After a brief confirmation, mark task done & close the drawer.
      setTimeout(() => {
        onDone();
        queryClient.invalidateQueries({ queryKey: ['important-emails'] });
        queryClient.invalidateQueries({ queryKey: ['priorities'] });
      }, 1400);
    } catch (err) {
      setSendError(
        err instanceof Error
          ? err.message
          : 'Send failed. Check the backend logs.',
      );
    } finally {
      setSendPending(false);
    }
  }

  async function handleSaveDraftReply() {
    if (!priority || !draft || savingDraft) return;
    setSavingDraft(true);
    setSendError(null);
    try {
      const ccString = ccIncluded.size > 0
        ? Array.from(ccIncluded).join(', ')
        : undefined;
      await saveEmailReplyAsDraft(priority.id, {
        to: draft.to,
        subject: draft.subject,
        body: draft.body,
        cc: ccString,
      });
      setSavedDraft(true);
    } catch (err) {
      setSendError(
        err instanceof Error ? err.message : 'Draft save failed. Check the backend logs.',
      );
    } finally {
      setSavingDraft(false);
    }
  }

  function toggleCcChip(addr: string) {
    setCcIncluded((prev) => {
      const next = new Set(prev);
      if (next.has(addr)) next.delete(addr);
      else next.add(addr);
      return next;
    });
  }

  function toggleReplyAll() {
    if (!draft) return;
    setCcIncluded((prev) =>
      prev.size === draft.originalCc.length ? new Set() : new Set(draft.originalCc),
    );
  }

  const emailBody = emailQuery.data?.body ?? '';
  const emailSender = emailQuery.data?.sender ?? '';

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-950/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <aside
        className="absolute right-0 top-0 bottom-0 w-full sm:max-w-xl bg-stone-950 border-l border-stone-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="flex items-center justify-between px-5 py-4 border-b border-stone-800 flex-shrink-0">
          <div className="min-w-0">
            <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
              Chat to solve
            </p>
            <h2 className="text-stone-100 text-sm font-semibold mt-0.5 truncate">
              {priority.title}
            </h2>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={onDone}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 px-3 py-1.5 rounded-lg hover:bg-emerald-500/10 border border-transparent hover:border-emerald-500/20 transition-all"
            >
              Mark done ✓
            </button>
            <button
              onClick={onClose}
              className="text-stone-600 hover:text-stone-300 text-xs px-2"
            >
              close
            </button>
          </div>
        </header>

        {/* Context block — collapsible for email tasks */}
        {isEmail && (
          <div className="px-5 py-3 border-b border-stone-800 bg-stone-900/40 flex-shrink-0 max-h-48 overflow-y-auto">
            <p className="text-stone-600 text-xs">
              From <span className="text-stone-400">{emailSender}</span>
            </p>
            {emailQuery.isLoading ? (
              <p className="text-stone-700 text-xs mt-2">Loading email…</p>
            ) : emailBody ? (
              <p className="text-stone-400 text-xs whitespace-pre-wrap leading-relaxed mt-2">
                {emailBody.slice(0, 1200)}
                {emailBody.length > 1200 ? '…' : ''}
              </p>
            ) : (
              <p className="text-stone-700 text-xs mt-2">
                (No body available — Marimba will work from the subject only.)
              </p>
            )}
          </div>
        )}

        {/* Chat thread */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {messages.length === 0 && !chatPending && (
            <p className="text-stone-700 text-xs">
              {isEmail ? (
                draftPending ? (
                  <>Marimba is drafting a reply for you…</>
                ) : draft ? (
                  <>
                    Draft ready below — edit and send, or chat here to refine
                    (e.g.{' '}
                    <span className="text-stone-600 italic">
                      "más corto", "en inglés", "responder solo que sí"
                    </span>
                    ).
                  </>
                ) : (
                  <>
                    Tell Marimba what you want to do.{' '}
                    <span className="text-stone-600 italic">
                      "draft a reply", "what is this person really asking?"
                    </span>
                  </>
                )
              ) : (
                <>
                  Tell Marimba what you want to do with this task. Examples:{' '}
                  <span className="text-stone-600 italic">
                    "do I really need to do this today?", "give me a 30-second
                    take", "break this into 2 steps"
                  </span>
                </>
              )}
            </p>
          )}
          {messages.map((m, i) => (
            <ChatMessageBubble
              key={i}
              role={m.role}
              content={m.content}
              toolCalls={m.tool_calls}
            />
          ))}
          {chatPending && (
            <div className="mr-auto max-w-[85%] bg-stone-900 border border-stone-800 text-stone-500 text-sm px-3 py-2 rounded-2xl rounded-bl-md">
              Marimba is thinking…
            </div>
          )}
          {chatError && (
            <p className="text-amber-500/80 text-xs">{chatError}</p>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Reply draft preview — only renders when one has been generated */}
        {draft && (
          <div className="px-5 py-4 border-t border-stone-800 bg-stone-900/50 space-y-2 flex-shrink-0">
            <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase">
              Draft reply — review before sending
            </p>
            <input
              value={draft.to}
              onChange={(e) => setDraft({ ...draft, to: e.target.value })}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-1.5 text-stone-300 text-xs focus:outline-none focus:border-stone-600"
              placeholder="To"
            />
            {/* CC row — only renders when the original email had CCs. Default
                is none selected (reply-to-sender-only); teacher taps chips to
                opt in, or "Reply all" to toggle them all on/off. */}
            {draft.originalCc.length > 0 && (
              <div className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <button
                    onClick={() => setCcExpanded((v) => !v)}
                    className="text-stone-500 hover:text-stone-300 text-xs flex items-center gap-1.5"
                  >
                    <span className="text-stone-600 text-[0.65rem] uppercase tracking-widest font-semibold">
                      Cc
                    </span>
                    <span className="text-stone-400">
                      {ccIncluded.size === 0
                        ? `${draft.originalCc.length} other${draft.originalCc.length === 1 ? '' : 's'} not included`
                        : `${ccIncluded.size} of ${draft.originalCc.length} included`}
                    </span>
                    <span className="text-stone-600">{ccExpanded ? '▾' : '▸'}</span>
                  </button>
                  <button
                    onClick={toggleReplyAll}
                    className="text-[0.7rem] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 px-2 py-0.5 rounded transition-all"
                  >
                    {ccIncluded.size === draft.originalCc.length ? 'Reply (sender only)' : 'Reply all'}
                  </button>
                </div>
                {ccExpanded && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {draft.originalCc.map((addr) => {
                      const included = ccIncluded.has(addr);
                      return (
                        <button
                          key={addr}
                          onClick={() => toggleCcChip(addr)}
                          className={`text-[0.7rem] px-2 py-0.5 rounded-full border transition-colors ${
                            included
                              ? 'bg-amber-500/20 border-amber-500/40 text-amber-200'
                              : 'bg-stone-900 border-stone-800 text-stone-500 hover:border-stone-700 hover:text-stone-400'
                          }`}
                          title={included ? 'Tap to exclude' : 'Tap to include'}
                        >
                          {included && <span className="mr-1">✓</span>}
                          {addr}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
            <input
              value={draft.subject}
              onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-1.5 text-stone-300 text-xs focus:outline-none focus:border-stone-600"
              placeholder="Subject"
            />
            <textarea
              value={draft.body}
              onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              rows={8}
              className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-stone-300 text-sm focus:outline-none focus:border-stone-600 resize-none"
            />
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-stone-600">
                {sentOK
                  ? 'Sent ✓'
                  : savedDraft
                  ? 'Draft saved to Gmail ✓'
                  : sendError
                  ? <span className="text-amber-500/80">{sendError}</span>
                  : ' '}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setDraft(null)}
                  disabled={sendPending || savingDraft || sentOK}
                  className="text-xs text-stone-500 hover:text-stone-300 px-2 disabled:opacity-40"
                >
                  discard
                </button>
                <button
                  onClick={handleSaveDraftReply}
                  disabled={savingDraft || sentOK || savedDraft || !draft.to || !draft.body}
                  className="text-xs text-stone-400 border border-stone-700 hover:border-stone-600 hover:text-stone-200 px-3 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-40"
                >
                  {savingDraft ? 'Saving…' : savedDraft ? 'Saved' : 'Save as draft'}
                </button>
                <button
                  onClick={handleSendReply}
                  disabled={sendPending || sentOK || !draft.to || !draft.body}
                  className="text-xs font-semibold text-amber-300 bg-amber-500/20 border border-amber-500/30 hover:bg-amber-500/30 px-3 py-1.5 rounded-lg transition-all active:scale-95 disabled:opacity-40"
                >
                  {sendPending ? 'Sending…' : sentOK ? 'Sent' : 'Send reply'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Composer + quick actions */}
        <footer className="px-5 py-4 border-t border-stone-800 space-y-2 flex-shrink-0">
          {isEmail && !draft && (
            <button
              onClick={handleDraftReply}
              disabled={draftPending}
              className="text-xs font-medium text-stone-400 hover:text-stone-200 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-all disabled:opacity-40"
            >
              {draftPending ? 'Drafting…' : 'Draft a reply'}
            </button>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message Marimba… (Enter to send, Shift+Enter for newline)"
              rows={2}
              className="flex-1 bg-stone-900 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-200 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || chatPending}
              className="text-xs font-semibold text-amber-300 bg-amber-500/20 border border-amber-500/30 hover:bg-amber-500/30 px-3 py-2.5 rounded-xl transition-all active:scale-95 disabled:opacity-40 self-stretch"
            >
              {chatPending ? '…' : 'Send'}
            </button>
          </div>
        </footer>
      </aside>
    </div>
  );
}
