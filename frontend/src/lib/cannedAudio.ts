/**
 * Plays a pre-rendered Marimba voice line from /public/audio/.
 * These are generated once by backend/scripts/render_canned_audio.py so we
 * don't pay an ElevenLabs API call (and its latency) on every fixed phrase.
 *
 * Fails silently — audio is a nice-to-have, never block the UI on it.
 */
export function playCannedAudio(filename: string): void {
  try {
    const audio = new Audio(`/audio/${filename}`);
    audio.play().catch(() => {
      // Autoplay can be blocked if no user gesture preceded this call.
      // We ignore the rejection — the action that triggered it is the
      // primary success signal; audio is a flourish.
    });
  } catch {
    // Browser without Audio support, or invalid URL — silently skip.
  }
}
