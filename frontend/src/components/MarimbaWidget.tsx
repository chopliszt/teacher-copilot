// ── State machine ────────────────────────────────────────────────────────────
//
//  idle       Default. Marimba breathes slowly.
//  listening  Mic is active. Amber ring pulses. Tap again to send.
//  thinking   Voxtral + Mistral processing. Dots bounce.
//  speaking   ElevenLabs audio playing. Avatar pulses.
//

export type MarimbaState = 'idle' | 'listening' | 'thinking' | 'speaking';

// ── Subtle audio feedback ────────────────────────────────────────────────────

function playTone(frequency: number, durationMs: number, volume = 0.15): void {
  try {
    const ctx = new AudioContext();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();

    oscillator.type = 'sine';
    oscillator.frequency.value = frequency;
    gain.gain.value = volume;
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);

    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.start();
    oscillator.stop(ctx.currentTime + durationMs / 1000);
  } catch {
    // Audio not available — fail silently
  }
}

function playStartTone(): void {
  playTone(600, 100, 0.12);
  setTimeout(() => playTone(900, 120, 0.12), 80);
}

function playSendTone(): void {
  playTone(1200, 80, 0.1);
}

function playDiscardTone(): void {
  playTone(400, 150, 0.08);
}

// ── Minimal SVG icons ────────────────────────────────────────────────────────

// Upward arrow — "send" feel, soft and minimal
function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </svg>
  );
}

// Small × — discard, minimal and unobtrusive
function DiscardIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

// ── Status label ──────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<MarimbaState, string> = {
  idle:      'tap to speak',
  listening: 'tap to send',
  thinking:  'thinking…',
  speaking:  'speaking',
};

// ── Thinking dots ─────────────────────────────────────────────────────────────

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
  listening: 'border-amber-400/60',
  thinking:  'border-amber-500/40',
  speaking:  'border-amber-400/60',
};

interface AvatarProps {
  state: MarimbaState;
  onClick: () => void;
  canClick: boolean;
}

function Avatar({ state, onClick, canClick }: AvatarProps) {
  function handleClick() {
    if (state === 'idle') {
      playStartTone();
    } else if (state === 'listening') {
      playSendTone();
    }
    onClick();
  }

  return (
    <div className="relative flex items-center justify-center">
      {/* Pulsing ring while listening */}
      {state === 'listening' && (
        <div
          className="absolute inset-0 rounded-full bg-amber-400/15"
          style={{ animation: 'marimba-ring-pulse 1.3s ease-out infinite' }}
        />
      )}

      <button
        onClick={handleClick}
        disabled={!canClick}
        style={AVATAR_ANIMATION[state]}
        className={`
          relative w-14 h-14 rounded-full
          bg-amber-500/10 border-2 ${AVATAR_RING[state]}
          flex items-center justify-center
          select-none transition-all duration-300
          ${canClick
            ? 'cursor-pointer hover:bg-amber-500/15 active:scale-95'
            : 'cursor-default'
          }
        `}
        aria-label={
          state === 'listening'
            ? 'Tap to send your message'
            : canClick
              ? 'Tap to speak to Marimba'
              : 'Marimba is busy'
        }
      >
        {state === 'listening' ? (
          <span className="text-amber-400">
            <SendIcon />
          </span>
        ) : (
          <span className="text-2xl">🦊</span>
        )}
      </button>
    </div>
  );
}

// ── Widget ────────────────────────────────────────────────────────────────────

interface MarimbaWidgetProps {
  state: MarimbaState;
  isSupported: boolean;
  onMicClick: () => void;
  onDiscard?: () => void;
  lastResponse: string | null;
}

export function MarimbaWidget({ state, isSupported, onMicClick, onDiscard, lastResponse }: MarimbaWidgetProps) {
  const canTap = isSupported && (state === 'idle' || state === 'listening');

  function handleDiscard() {
    playDiscardTone();
    onDiscard?.();
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">

      {/* Speech bubble — always shown when there's a response */}
      {lastResponse && (
        <div className="relative max-w-[220px] mb-1">
          <div className="bg-stone-800 border border-stone-700 rounded-2xl rounded-br-sm px-3.5 py-2.5 shadow-lg">
            <p className="text-stone-200 text-xs leading-relaxed">{lastResponse}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col items-center gap-2">
        {state === 'thinking' && <ThinkingDots />}

        {/* Avatar + discard grouped tightly together */}
        <div className="relative">
          <Avatar state={state} onClick={onMicClick} canClick={canTap} />

          {/* Discard button — small × tucked into the top-left of the avatar */}
          {state === 'listening' && onDiscard && (
            <button
              onClick={handleDiscard}
              className="
                absolute -top-1 -left-1
                w-6 h-6 rounded-full
                bg-stone-800/90 border border-stone-600/50
                flex items-center justify-center
                text-stone-500 hover:text-stone-300 hover:border-stone-500
                transition-all duration-200 active:scale-90
                cursor-pointer backdrop-blur-sm
              "
              aria-label="Discard recording"
              title="Discard"
            >
              <DiscardIcon />
            </button>
          )}
        </div>

        {/* Status label */}
        <p className={`
          text-xs transition-colors duration-300 select-none
          ${state === 'listening' ? 'text-amber-400/80' : 'text-stone-600'}
        `}>
          {isSupported ? STATUS_LABEL[state] : 'mic unavailable'}
        </p>
      </div>
    </div>
  );
}
