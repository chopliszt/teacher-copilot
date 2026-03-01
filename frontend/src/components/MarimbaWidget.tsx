// ── State machine ────────────────────────────────────────────────────────────
//
//  idle       Default. Marimba breathes slowly.
//  listening  Mic is active. Amber ring pulses. Tap again to stop.
//  thinking   Voxtral + Mistral processing. Dots bounce.
//  speaking   ElevenLabs audio playing. Avatar pulses.
//

export type MarimbaState = 'idle' | 'listening' | 'thinking' | 'speaking';

// ── Status label ──────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<MarimbaState, string> = {
  idle:      'tap to speak',
  listening: 'listening… tap to stop',
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
  listening: 'border-amber-400/80',
  thinking:  'border-amber-500/40',
  speaking:  'border-amber-400/60',
};

interface AvatarProps {
  state: MarimbaState;
  onClick: () => void;
  canClick: boolean;
}

function Avatar({ state, onClick, canClick }: AvatarProps) {
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
        onClick={onClick}
        disabled={!canClick}
        style={AVATAR_ANIMATION[state]}
        className={`
          relative w-14 h-14 rounded-full
          bg-amber-500/10 border-2 ${AVATAR_RING[state]}
          flex items-center justify-center text-2xl
          select-none transition-colors duration-300
          ${canClick
            ? 'cursor-pointer hover:bg-amber-500/15 active:scale-95'
            : 'cursor-default'
          }
        `}
        aria-label={canClick ? 'Tap to speak to Marimba' : 'Marimba is busy'}
      >
        🦊
      </button>
    </div>
  );
}

// ── Mic button removed (handled entirely by Avatar) ──

// ── Widget ────────────────────────────────────────────────────────────────────

interface MarimbaWidgetProps {
  state: MarimbaState;
  isSupported: boolean;
  onMicClick: () => void;
  lastResponse: string | null;
}

export function MarimbaWidget({ state, isSupported, onMicClick, lastResponse }: MarimbaWidgetProps) {
  const canTap = isSupported && (state === 'idle' || state === 'listening');

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">

      {/* Speech bubble — always shown when there's a response, audio or not */}
      {lastResponse && (
        <div className="relative max-w-[220px] mb-1">
          <div className="bg-stone-800 border border-stone-700 rounded-2xl rounded-br-sm px-3.5 py-2.5 shadow-lg">
            <p className="text-stone-200 text-xs leading-relaxed">{lastResponse}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col items-center gap-2">
        {state === 'thinking' && <ThinkingDots />}

        <Avatar state={state} onClick={onMicClick} canClick={canTap} />

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
