import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  chatWithTask,
  draftEmailReply,
  fetchEmailDetail,
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
}

export function TaskChatDrawer({ priority, onClose, onDone }: TaskChatDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [chatPending, setChatPending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [draftPending, setDraftPending] = useState(false);
  const [sendPending, setSendPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sentOK, setSentOK] = useState(false);

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
  }, [priority?.id]);

  // Auto-scroll the chat thread as new messages arrive.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, draft]);

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
      setDraft({ to: result.to, subject: result.subject, body: result.body });
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
      await sendEmailReply(priority.id, draft);
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
              Tell Marimba what you want to do with this task. Examples:{' '}
              <span className="text-stone-600 italic">
                {isEmail
                  ? '"draft a friendly reply", "what is this person really asking?", "give me a 2-line response in Spanish"'
                  : '"do I really need to do this today?", "give me a 30-second take", "break this into 2 steps"'}
              </span>
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
                  : sendError
                  ? <span className="text-amber-500/80">{sendError}</span>
                  : ' '}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setDraft(null)}
                  disabled={sendPending || sentOK}
                  className="text-xs text-stone-500 hover:text-stone-300 px-2 disabled:opacity-40"
                >
                  discard
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
