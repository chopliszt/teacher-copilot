import { useEffect, useRef, useState } from 'react';
import {
  fetchRecentLessonPlans,
  lessonPlanAssignment,
  lessonPlanChat,
  saveLessonPlan,
  type ChatMessage,
  type LessonContextSnapshot,
  type RecentLessonPlan,
} from '../lib/api/client';
import { ChatMessageBubble } from './ChatMessageBubble';

interface LessonPlanDrawerProps {
  group: string | null;
  onClose: () => void;
}

/**
 * "Plan lesson" drawer — Marimba pre-loads three distinct proposals (or a
 * Socratic question if there's no history yet), the teacher picks/refines
 * via chat, and the final ```lesson block can be saved against the group/date.
 *
 * Mirrors TaskChatDrawer in structure: slide-in right panel, chat thread on
 * top, action row in the footer. Extra footer actions specific to this flow:
 * Save & close · Copy as prompt · Generate assignment description.
 */
export function LessonPlanDrawer({ group, onClose }: LessonPlanDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [chatPending, setChatPending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<LessonContextSnapshot | null>(null);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [assignmentPending, setAssignmentPending] = useState(false);
  const [recentPlans, setRecentPlans] = useState<RecentLessonPlan[]>([]);

  const [copyToast, setCopyToast] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Reset state whenever the drawer opens on a new group.
  useEffect(() => {
    setMessages([]);
    setInput('');
    setChatPending(false);
    setChatError(null);
    setSnapshot(null);
    setSaving(false);
    setSaved(false);
    setSaveError(null);
    setAssignmentPending(false);
    setRecentPlans([]);
    setCopyToast(false);
  }, [group]);

  // Auto-scroll on new messages.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length]);

  // Escape closes the drawer (consistent with TaskChatDrawer).
  useEffect(() => {
    if (!group) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [group, onClose]);

  // First-turn auto-open: as soon as the drawer mounts for a group, ask the
  // backend to produce Marimba's opener (3 proposals OR Socratic question).
  useEffect(() => {
    if (!group) return;
    let cancelled = false;
    (async () => {
      setChatPending(true);
      setChatError(null);
      try {
        const result = await lessonPlanChat(group, []);
        if (cancelled) return;
        setSnapshot(result.context_snapshot);
        setMessages([{ role: 'assistant', content: result.reply }]);
        // Fetch recent plans for the small "previous plans" hint at the top.
        fetchRecentLessonPlans(group, 3)
          .then((plans) => !cancelled && setRecentPlans(plans))
          .catch(() => {});
      } catch (err) {
        if (cancelled) return;
        setChatError(
          err instanceof Error
            ? err.message
            : 'No pude contactar a Marimba. Probá de nuevo.',
        );
      } finally {
        if (!cancelled) setChatPending(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [group]);

  if (!group) return null;

  // The "current plan" is implicit: the latest ```lesson block in the thread.
  // We extract it on demand for save / copy / assignment actions.
  const latestLessonText = extractLatestFencedBlock(messages, 'lesson');

  async function handleSend() {
    if (!group) return;
    const text = input.trim();
    if (!text || chatPending) return;

    const next: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setChatPending(true);
    setChatError(null);

    try {
      const result = await lessonPlanChat(
        group,
        next.map((m) => ({ role: m.role, content: m.content })),
      );
      setSnapshot(result.context_snapshot);
      setMessages([...next, { role: 'assistant', content: result.reply }]);
    } catch (err) {
      setChatError(
        err instanceof Error
          ? err.message
          : 'No pude contactar a Marimba. Probá de nuevo.',
      );
      setMessages(messages);
      setInput(text);
    } finally {
      setChatPending(false);
    }
  }

  async function handleSave() {
    if (!group || !latestLessonText || saving || saved) return;
    setSaving(true);
    setSaveError(null);
    try {
      const todayIso = new Date().toISOString().slice(0, 10);
      await saveLessonPlan(group, {
        date: todayIso,
        plan_text: latestLessonText,
        context_snapshot: snapshot,
        chosen_option: detectChosenOption(messages),
      });
      setSaved(true);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : 'No se pudo guardar la propuesta.',
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateAssignment() {
    if (!group || !latestLessonText || assignmentPending) return;
    setAssignmentPending(true);
    try {
      const result = await lessonPlanAssignment(group, latestLessonText);
      setMessages((m) => [...m, { role: 'assistant', content: result.reply }]);
    } catch (err) {
      setChatError(
        err instanceof Error
          ? err.message
          : 'No pude generar la descripción del entregable.',
      );
    } finally {
      setAssignmentPending(false);
    }
  }

  async function handleCopyAsPrompt() {
    if (!latestLessonText || !snapshot) return;
    const promptText = buildExternalPrompt({
      group,
      snapshot,
      planText: latestLessonText,
    });
    try {
      await navigator.clipboard.writeText(promptText);
      setCopyToast(true);
      setTimeout(() => setCopyToast(false), 1800);
    } catch {
      // Older browsers fallback
      const ta = document.createElement('textarea');
      ta.value = promptText;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        setCopyToast(true);
        setTimeout(() => setCopyToast(false), 1800);
      } finally {
        document.body.removeChild(ta);
      }
    }
  }

  const canActOnPlan = !!latestLessonText;

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
              Plan lesson
            </p>
            <h2 className="text-stone-100 text-sm font-semibold mt-0.5 truncate">
              {group}
              {snapshot?.subject && (
                <span className="text-stone-500 font-normal">
                  {' · '}
                  {snapshot.subject}
                </span>
              )}
              {snapshot?.duration_min && (
                <span className="text-stone-600 font-normal">
                  {' · '}
                  {snapshot.duration_min} min
                </span>
              )}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-stone-600 hover:text-stone-300 text-xs px-2 flex-shrink-0"
          >
            close
          </button>
        </header>

        {/* Recent plans hint */}
        {recentPlans.length > 0 && (
          <div className="px-5 py-2 border-b border-stone-800 bg-stone-900/40 flex-shrink-0">
            <p className="text-stone-600 text-[0.65rem] uppercase tracking-widest font-semibold mb-1">
              Last planned
            </p>
            <p className="text-stone-500 text-xs truncate">
              {recentPlans
                .map((p) => `${p.date.slice(5)}: ${firstLine(p.plan_text)}`)
                .slice(0, 2)
                .join(' · ')}
            </p>
          </div>
        )}

        {/* Chat thread */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {chatPending && messages.length === 0 && (
            <p className="text-stone-500 text-sm italic">
              Marimba está pensando en propuestas…
            </p>
          )}
          {messages.map((m, i) => (
            <ChatMessageBubble key={i} role={m.role} content={m.content} />
          ))}
          {chatPending && messages.length > 0 && (
            <div className="mr-auto max-w-[85%] bg-stone-900 border border-stone-800 text-stone-500 text-sm px-3 py-2 rounded-2xl rounded-bl-md">
              Marimba está pensando…
            </div>
          )}
          {chatError && (
            <p className="text-amber-500/80 text-xs">{chatError}</p>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Plan-action toolbar — only enabled when a ```lesson block exists */}
        <div className="px-5 py-3 border-t border-stone-800 bg-stone-900/40 flex-shrink-0 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleSave}
              disabled={!canActOnPlan || saving || saved}
              className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/15 px-3 py-1.5 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title={!canActOnPlan ? 'Refiná la propuesta primero' : 'Save the proposed plan'}
            >
              {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save & close'}
            </button>
            <button
              onClick={handleCopyAsPrompt}
              disabled={!canActOnPlan}
              className="text-xs font-medium text-stone-400 hover:text-stone-200 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              title="Copy a context-rich prompt to paste into Claude or ChatGPT"
            >
              {copyToast ? '✓ Copied' : 'Copy as prompt'}
            </button>
            <button
              onClick={handleGenerateAssignment}
              disabled={!canActOnPlan || assignmentPending}
              className="text-xs font-medium text-stone-400 hover:text-stone-200 border border-stone-800 hover:border-stone-700 px-3 py-1.5 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {assignmentPending ? 'Generando…' : '+ Assignment description'}
            </button>
          </div>
          {saveError && (
            <p className="text-amber-500/80 text-xs">{saveError}</p>
          )}
          {!canActOnPlan && messages.length > 0 && !chatPending && (
            <p className="text-stone-700 text-[0.7rem] italic">
              Elegí una opción o proponé tu dirección para que Marimba arme la propuesta completa.
            </p>
          )}
        </div>

        {/* Composer */}
        <footer className="px-5 py-4 border-t border-stone-800 flex-shrink-0">
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
              placeholder='Ej. "opción 2 pero más corto", "agregá 5 min de feedback al final"…'
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

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Pull the most recent fenced code block with the given language tag from
 * the chat thread (e.g. ```lesson, ```assignment). Returns the body text
 * (without fences), or null if no such block exists yet.
 */
function extractLatestFencedBlock(
  messages: ChatMessage[],
  lang: string,
): string | null {
  const pattern = new RegExp('```' + lang + '\\s*\\n([\\s\\S]*?)\\n```', 'g');
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== 'assistant') continue;
    const matches = [...m.content.matchAll(pattern)];
    if (matches.length > 0) {
      return matches[matches.length - 1][1].trim();
    }
  }
  return null;
}

/**
 * Inspect the FIRST user message — if it looks like "1", "2", "3", "opción 1",
 * etc., record which numbered option the teacher picked. Saved so future ML
 * can learn which proposal style the teacher tends to choose.
 */
function detectChosenOption(messages: ChatMessage[]): number | null {
  const firstUser = messages.find((m) => m.role === 'user');
  if (!firstUser) return null;
  const m = firstUser.content
    .trim()
    .toLowerCase()
    .match(/^(?:opci[oó]n\s*|option\s*)?([1-3])(?:\b|[^0-9])/);
  return m ? parseInt(m[1], 10) : null;
}

function firstLine(s: string): string {
  const line = s.trim().split('\n').find((ln) => ln.trim().length > 0) ?? '';
  return line.length > 60 ? line.slice(0, 60) + '…' : line;
}

/**
 * Build the "copy as prompt" payload for Claude/ChatGPT — pre-loaded with
 * full lesson context + a placeholder where the teacher writes the specific
 * downstream ask (handout, worksheet, quiz, etc.).
 */
function buildExternalPrompt(args: {
  group: string;
  snapshot: LessonContextSnapshot;
  planText: string;
}): string {
  const { group, snapshot, planText } = args;
  const lastSession = snapshot.last_sessions[0];
  const lastSessionLine = lastSession
    ? `\nÚltima sesión: "${lastSession.notes}"${lastSession.what_worked ? ` (lo que funcionó: ${lastSession.what_worked})` : ''}`
    : '';

  return [
    `Soy profe de ${snapshot.subject || 'mis estudiantes'} en un colegio bilingüe en Costa Rica.`,
    `Estoy planeando la clase de ${group} (${snapshot.duration_min} min, hoy a las ${snapshot.time_label || '...'}).`,
    lastSessionLine.trim(),
    '',
    'Esta es la propuesta de plan de hoy:',
    '',
    planText,
    '',
    'Necesito que [REEMPLAZÁ ESTO: describí el artefacto que querés — ej. "armes un handout para los estudiantes", "generes un quiz formativo de 5 preguntas", "me expliques cómo evaluar la actividad principal"]',
  ]
    .filter(Boolean)
    .join('\n');
}
