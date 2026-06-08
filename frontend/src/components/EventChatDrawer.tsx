import { useEffect, useRef, useState } from 'react';
import { chatWithTask, type ChatMessage, type CalendarEvent } from '../lib/api/client';
import { ChatMessageBubble } from './ChatMessageBubble';

interface EventChatDrawerProps {
  event: CalendarEvent | null;
  onClose: () => void;
}

// "Chat about this" — a text-first conversation with Marimba about one event.
// The event is preloaded as context server-side (chat_task, source="event"), so
// the teacher can jump straight to "help me prep" / "move it" without re-typing
// what the meeting is. Reuses the same chat bubble + backend as the task drawer.
export function EventChatDrawer({ event, onClose }: EventChatDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fresh thread whenever a different event opens.
  useEffect(() => {
    setMessages([]);
    setInput('');
    setError(null);
  }, [event?.id]);

  // Auto-scroll as messages arrive.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, pending]);

  // Close on Escape, like a native modal.
  useEffect(() => {
    if (!event) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [event, onClose]);

  if (!event) return null;

  async function send(text: string, history: ChatMessage[]) {
    if (!event) return;
    setPending(true);
    setError(null);
    try {
      const result = await chatWithTask({
        task_id: event.id,
        source: 'event',
        title: event.title,
        messages: history.map((m) => ({ role: m.role, content: m.content })),
      });
      setMessages([...history, { role: 'assistant', content: result.reply, tool_calls: result.tool_calls }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Marimba could not respond. Try again.');
      setMessages(history.filter((m) => m.role !== 'user' || history.indexOf(m) < history.length - 1));
    } finally {
      setPending(false);
    }
  }

  function handleSend() {
    const text = input.trim();
    if (!text || pending) return;
    const next: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    send(text, next);
  }

  const timeLabel = event.start_time
    ? `${event.start_time}${event.end_time ? `–${event.end_time}` : ''}`
    : 'All day';

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/70 backdrop-blur-sm" onClick={onClose}>
      <aside
        className="absolute right-0 top-0 bottom-0 w-full sm:max-w-xl bg-stone-950 border-l border-stone-800 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-stone-800 flex-shrink-0">
          <div className="min-w-0">
            <p className="text-stone-600 text-xs font-semibold tracking-widest uppercase">Chat about this</p>
            <h2 className="text-stone-100 text-sm font-semibold mt-0.5 truncate">{event.title}</h2>
            <p className="text-stone-600 text-xs mt-0.5">
              {timeLabel}{event.location ? ` · ${event.location}` : ''}
            </p>
          </div>
          <button onClick={onClose} className="text-stone-600 hover:text-stone-300 text-xs px-2 flex-shrink-0">
            close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {messages.length === 0 && !pending && (
            <p className="text-stone-700 text-xs">
              Ask Marimba anything about this meeting.{' '}
              <span className="text-stone-600 italic">
                "help me prep", "what's this about?", "add it to my calendar"
              </span>
            </p>
          )}
          {messages.map((m, i) => (
            <ChatMessageBubble key={i} role={m.role} content={m.content} toolCalls={m.tool_calls} />
          ))}
          {pending && (
            <div className="mr-auto max-w-[85%] bg-stone-900 border border-stone-800 text-stone-500 text-sm px-3 py-2 rounded-2xl rounded-bl-md">
              Marimba is thinking…
            </div>
          )}
          {error && <p className="text-amber-500/80 text-xs">{error}</p>}
          <div ref={messagesEndRef} />
        </div>

        <footer className="px-5 py-4 border-t border-stone-800 flex-shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
              }}
              placeholder="Message Marimba… (Enter to send, Shift+Enter for newline)"
              rows={2}
              className="flex-1 bg-stone-900 border border-stone-800 rounded-xl px-3 py-2.5 text-stone-200 text-sm placeholder-stone-700 resize-none focus:outline-none focus:border-stone-600"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || pending}
              className="text-xs font-semibold text-amber-300 bg-amber-500/20 border border-amber-500/30 hover:bg-amber-500/30 px-3 py-2.5 rounded-xl transition-all active:scale-95 disabled:opacity-40 self-stretch"
            >
              {pending ? '…' : 'Send'}
            </button>
          </div>
        </footer>
      </aside>
    </div>
  );
}
