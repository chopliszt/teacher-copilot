import { useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { parseEmailArtifact } from '../lib/parseEmailArtifact';
import { EmailComposer } from './EmailComposer';
import type { ChatToolCall } from '../lib/api/client';

interface ChatMessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ChatToolCall[];
}

const TOOL_LABEL: Record<string, string> = {
  search_sent_emails: 'Searched sent emails',
  search_inbox: 'Searched inbox',
  get_full_email: 'Opened email',
};

function ToolCallChips({ toolCalls }: { toolCalls: ChatToolCall[] }) {
  if (!toolCalls.length) return null;
  return (
    <div className="mr-auto max-w-[90%] space-y-1 mb-1">
      {toolCalls.map((tc, i) => (
        <ToolCallChip key={i} call={tc} />
      ))}
    </div>
  );
}

function ToolCallChip({ call }: { call: ChatToolCall }) {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABEL[call.name] ?? call.name;
  const query = (call.args?.query as string) || (call.args?.message_id as string) || '';
  const detail = call.error
    ? `error: ${call.error}`
    : call.result_count != null
    ? `${call.result_count} match${call.result_count === 1 ? '' : 'es'}`
    : 'done';
  const hasMatches = (call.matches?.length ?? 0) > 0;

  return (
    <div>
      <button
        onClick={() => hasMatches && setOpen((o) => !o)}
        disabled={!hasMatches}
        className={`inline-flex items-center gap-1.5 text-[0.7rem] text-stone-500 bg-stone-900/60 border border-stone-800 rounded-full px-2 py-0.5 ${hasMatches ? 'hover:border-stone-700 cursor-pointer' : 'cursor-default'}`}
        title={query ? `query: ${query}` : undefined}
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-amber-400/70">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <span className="text-stone-400">{label}</span>
        {query && (
          <span className="text-stone-600 italic truncate max-w-[140px]">
            “{query}”
          </span>
        )}
        <span className="text-stone-600">· {detail}</span>
        {hasMatches && (
          <svg
            width="9" height="9" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
            className={`text-stone-600 transition-transform ${open ? 'rotate-180' : ''}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        )}
      </button>
      {open && hasMatches && (
        <ul className="mt-1 ml-3 space-y-0.5 text-[0.7rem]">
          {call.matches!.map((m, i) => (
            <li key={`${m.id}-${i}`} className="text-stone-500 truncate">
              <span className="text-stone-300">{m.subject || '(no subject)'}</span>
              {m.from && (
                <span className="text-stone-600"> · {senderShort(m.from)}</span>
              )}
              {m.date && (
                <span className="text-stone-700"> · {m.date.slice(0, 10)}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function senderShort(raw: string): string {
  const match = raw.match(/^([^<]+?)\s*<.+>$/);
  if (match) return match[1].trim();
  return raw;
}

/**
 * One bubble in the task chat thread.
 *
 * User messages render as plain text (no markdown surprises from input).
 * Assistant messages render markdown via react-markdown + GFM (tables,
 * task lists, strikethrough). Fenced code blocks render as a styled
 * "artifact card" with a Copy button so the teacher can lift prompts /
 * drafts / handouts in one tap — Marimba is instructed in the system
 * prompt to use code fences whenever output is meant to be copied.
 *
 * Every assistant bubble also exposes a top-level Copy button that copies
 * the entire message (raw markdown), which is handy when the response
 * is conversational but the teacher wants to lift the whole thing.
 */
export function ChatMessageBubble({ role, content, toolCalls }: ChatMessageBubbleProps) {
  if (role === 'user') {
    return (
      <div className="ml-auto max-w-[85%] bg-amber-500/10 border border-amber-500/20 text-stone-200 text-sm px-3 py-2 rounded-2xl rounded-br-md whitespace-pre-wrap">
        {content}
      </div>
    );
  }

  // Hide the bubble-level "copy reply" button when the message contains an
  // email composer — the composer is the action surface, not text to copy,
  // and the duplicate button visually competes with the Send button.
  const hasEmailComposer = /```email\b/.test(content);

  return (
    <div>
      {toolCalls && toolCalls.length > 0 && <ToolCallChips toolCalls={toolCalls} />}
      <div className="mr-auto max-w-[90%] min-w-0 bg-stone-900 border border-stone-800 text-stone-300 text-sm rounded-2xl rounded-bl-md group">
        {!hasEmailComposer && (
          <div className="px-3 pt-2 pb-1 flex items-center justify-end">
            <CopyButton text={content} label="copy reply" />
          </div>
        )}
        <div className={`px-3 pb-3 prose-marimba ${hasEmailComposer ? 'pt-3' : ''}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={MARKDOWN_COMPONENTS}
          >
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Older browsers / insecure context: fall back to a hidden textarea.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); setCopied(true); setTimeout(() => setCopied(false), 1500); }
      finally { document.body.removeChild(ta); }
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="text-xs text-stone-600 hover:text-stone-300 opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1"
      aria-label={label ?? 'Copy'}
    >
      {copied ? (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>copied</span>
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          <span>copy</span>
        </>
      )}
    </button>
  );
}

// ── Custom markdown component overrides ───────────────────────────────────────
//
// We keep most defaults (paragraphs, lists, tables, bold, italic) and only
// override the two cases that need our own look-and-feel:
//   - Fenced code blocks  → artifact card with a Copy button
//   - Inline code         → monospace pill, no background bleed

type CodeProps = {
  inline?: boolean;
  className?: string;
  children?: ReactNode;
};

function CodeBlock({ inline, className, children }: CodeProps) {
  const text = String(children ?? '').replace(/\n$/, '');
  if (inline) {
    return (
      <code className="bg-stone-950 text-amber-300/90 px-1.5 py-0.5 rounded text-[0.85em] font-mono">
        {children}
      </code>
    );
  }

  // The language tag (```prompt, ```handout, …) hints what kind of artifact
  // this is — show it as the card header so the teacher knows what they're
  // about to copy.
  const language = className?.replace(/^language-/, '') || 'artifact';

  // Special-case: ```email blocks become a real composer with Send + attachments.
  // Falls through to the generic artifact card if parsing fails.
  if (language === 'email') {
    const parsed = parseEmailArtifact(text);
    if (parsed) return <EmailComposer initial={parsed} />;
  }

  const headerLabel = LANGUAGE_LABEL[language] ?? language;

  return (
    <div className="my-3 rounded-xl border border-amber-500/20 bg-stone-950 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 bg-amber-500/5 border-b border-amber-500/15">
        <span className="text-amber-400/80 text-[0.7rem] font-semibold tracking-widest uppercase">
          {headerLabel}
        </span>
        <CopyButton text={text} label={`Copy ${headerLabel.toLowerCase()}`} />
      </div>
      <pre className="px-3 py-2.5 text-stone-200 text-xs leading-relaxed whitespace-pre-wrap break-words font-mono overflow-x-auto">
        {text}
      </pre>
    </div>
  );
}

const LANGUAGE_LABEL: Record<string, string> = {
  prompt: 'Prompt — copy and paste',
  handout: 'Handout',
  draft: 'Draft',
  email: 'Email body',
  lesson: 'Lesson plan — propuesta',
  assignment: 'Assignment description',
  artifact: 'Copyable',
};

const MARKDOWN_COMPONENTS = {
  code: CodeBlock,
  p: ({ children }: { children?: ReactNode }) => (
    <p className="text-stone-300 text-sm leading-relaxed my-1.5">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="list-disc list-outside ml-5 my-1.5 space-y-1 text-stone-300 text-sm">
      {children}
    </ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="list-decimal list-outside ml-5 my-1.5 space-y-1 text-stone-300 text-sm">
      {children}
    </ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="text-stone-100 font-semibold">{children}</strong>
  ),
  em: ({ children }: { children?: ReactNode }) => (
    <em className="text-stone-200 italic">{children}</em>
  ),
  h1: ({ children }: { children?: ReactNode }) => (
    <h3 className="text-stone-100 font-semibold text-sm mt-3 mb-1">{children}</h3>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h3 className="text-stone-100 font-semibold text-sm mt-3 mb-1">{children}</h3>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h4 className="text-stone-100 font-semibold text-sm mt-2 mb-1">{children}</h4>
  ),
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="border-l-2 border-stone-700 pl-3 my-1.5 text-stone-400 italic">
      {children}
    </blockquote>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="my-2 overflow-x-auto">
      <table className="text-xs border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border border-stone-800 px-2 py-1 text-stone-300 font-semibold text-left">
      {children}
    </th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border border-stone-800 px-2 py-1 text-stone-400">{children}</td>
  ),
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-amber-400 underline hover:text-amber-300">
      {children}
    </a>
  ),
};
