import { useState } from 'react';

// ── State machine ────────────────────────────────────────────────────────────
//
//  idle       Default. Marimba breathes slowly.
//  listening  Mic is active. Amber ring pulses. (Voxtral wires in here)
//  thinking   Processing. Dots bounce above avatar. (Triggered after transcription)
//  speaking   ElevenLabs audio playing. Avatar pulses with speech rhythm.
//
// Future — fullscreen mode:
//   handleAvatarClick will animate this widget to fill the screen,
//   activating the live assistant interface. The state machine is the same;
//   only the container size and layout change.

export type MarimbaState = 'idle' | 'listening' | 'thinking' | 'speaking';

// ── Thinking dots ────────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex gap-1 items-end justify-center h-4 mb-1">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-amber-400"
          style={{
            animation: `marimba-dot-bounce 1.2s ease-in-out ${i * 0.18}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

// ── Avatar bubble ─────────────────────────────────────────────────────────────

const AVATAR_ANIMATION: Record<MarimbaState, React.CSSProperties> = {
  idle:      { animation: 'marimba-breathe 4s ease-in-out infinite' },
  listening: { animation: 'none' },
  thinking:  { animation: 'marimba-breathe 2s ease-in-out infinite' },
  speaking:  { animation: 'marimba-speak 0.45s ease-in-out infinite' },
};

const AVATAR_RING: Record<MarimbaState, string> = {
  idle:      'border-amber-500/20',
  listening: 'border-amber-400/70',
  thinking:  'border-amber-500/30',
  speaking:  'border-amber-400/50',
};

interface AvatarProps {
  state: MarimbaState;
  onClick: () => void;
}

function Avatar({ state, onClick }: AvatarProps) {
  return (
    <div className="relative flex items-center justify-center">
      {/* Listening ring — expands and fades behind the bubble */}
      {state === 'listening' && (
        <div
          className="absolute inset-0 rounded-full bg-amber-400/15"
          style={{ animation: 'marimba-ring-pulse 1.3s ease-out infinite' }}
        />
      )}

      <button
        onClick={onClick}
        style={AVATAR_ANIMATION[state]}
        className={`
          relative w-14 h-14 rounded-full
          bg-amber-500/10 border-2 ${AVATAR_RING[state]}
          flex items-center justify-center text-2xl
          cursor-pointer select-none
          transition-colors duration-300
          hover:bg-amber-500/15 active:scale-95
        `}
        aria-label="Marimba — tap for full assistant"
      >
        🦊
      </button>
    </div>
  );
}

// ── Mic button ────────────────────────────────────────────────────────────────

interface MicButtonProps {
  active: boolean;
  onClick: () => void;
}

function MicButton({ active, onClick }: MicButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`
        w-9 h-9 rounded-full flex items-center justify-center
        border transition-all duration-200
        ${active
          ? 'bg-amber-500/20 border-amber-400/60 text-amber-400'
          : 'bg-stone-900 border-stone-700 text-stone-500 hover:text-stone-400 hover:border-stone-600'
        }
      `}
      aria-label={active ? 'Stop listening' : 'Speak to Marimba'}
    >
      <svg
        width="14" height="14" viewBox="0 0 24 24"
        fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8"  y1="23" x2="16" y2="23" />
      </svg>
    </button>
  );
}

// ── Widget ────────────────────────────────────────────────────────────────────

export function MarimbaWidget() {
  const [state, setState] = useState<MarimbaState>('idle');

  const handleMicClick = () => {
    // Stub — Voxtral Realtime integration wires in here.
    // When connected: start/stop transcription stream, then setState('thinking')
    // when the transcript is sent to Mistral, then setState('speaking') during playback.
    setState((prev) => (prev === 'listening' ? 'idle' : 'listening'));
  };

  const handleAvatarClick = () => {
    // Future: fullscreen live assistant mode.
    // Will transition this widget to fill the screen with a CSS animation,
    // revealing the full voice interface and activating the conversation.
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-center gap-2">
      {state === 'thinking' && <ThinkingDots />}
      <Avatar state={state} onClick={handleAvatarClick} />
      <MicButton active={state === 'listening'} onClick={handleMicClick} />
    </div>
  );
}
