import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { callVoice, type VoiceAction } from '../api/client';
import type { MarimbaState } from '../../components/MarimbaWidget';

interface UseVoiceOptions {
  onAction?: (action: VoiceAction) => void;
}

interface UseVoiceReturn {
  marimbaState: MarimbaState;
  toggleListening: () => void;
  discardRecording: () => void;
  isSupported: boolean;
  lastResponse: string | null;
}

// ── Audio format detection ────────────────────────────────────────────────────

function getSupportedMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',  // Chrome, Firefox, Edge
    'audio/webm',               // Chrome fallback
    'audio/mp4',                // Safari / iOS
    'audio/ogg;codecs=opus',    // Firefox fallback
  ];
  for (const type of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return '';
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useVoice({ onAction }: UseVoiceOptions = {}): UseVoiceReturn {
  const [marimbaState, setMarimbaState] = useState<MarimbaState>('idle');
  const [lastResponse, setLastResponse] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();

  const showResponse = useCallback((text: string, autoDismissMs = 6000) => {
    setLastResponse(text);
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    dismissTimerRef.current = setTimeout(() => setLastResponse(null), autoDismissMs);
  }, []);

  const isSupported =
    typeof window !== 'undefined' &&
    typeof MediaRecorder !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia;

  const handleAudioBlob = useCallback(
    async (blob: Blob) => {
      if (!blob.size) {
        console.warn('[Marimba] Audio blob is empty — recording may have been too short');
        setMarimbaState('idle');
        return;
      }

      console.log(`[Marimba] Sending audio to backend (${(blob.size / 1024).toFixed(1)} KB, type: ${blob.type})`);
      setMarimbaState('thinking');

      try {
        const result = await callVoice(blob);
        console.log('[Marimba] Response:', result);

        // Always show the text response — audio is a bonus, not required
        showResponse(result.text);

        // Handle action — add_task was already saved by backend, just refresh queries
        if (result.action) {
          console.log('[Marimba] Action:', result.action);
          if (result.action.type === 'add_task') {
            queryClient.invalidateQueries({ queryKey: ['user-tasks'] });
            queryClient.invalidateQueries({ queryKey: ['priorities'] });
          }
          onAction?.(result.action);
        }

        if (result.audio) {
          setMarimbaState('speaking');

          const audio = new Audio(`data:audio/mpeg;base64,${result.audio}`);
          audioRef.current = audio;

          audio.onended = () => {
            audioRef.current = null;
            setMarimbaState('idle');
          };
          audio.onerror = () => {
            console.warn('[Marimba] Audio playback error');
            audioRef.current = null;
            setMarimbaState('idle');
          };

          await audio.play().catch((err) => {
            console.warn('[Marimba] Autoplay blocked:', err);
            setMarimbaState('idle');
          });
        } else {
          console.log('[Marimba] No audio in response — text only');
          setMarimbaState('idle');
        }
      } catch (err) {
        console.error('[Marimba] Voice pipeline error:', err);
        showResponse('Algo salió mal, profe. Intenta de nuevo.');
        setMarimbaState('idle');
      }
    },
    [onAction, queryClient, showResponse],
  );

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      // onStop fires asynchronously — state transitions happen there
    }
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getSupportedMimeType();

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        // Stop all mic tracks to release the indicator in the browser tab
        stream.getTracks().forEach((t) => t.stop());

        const blob = new Blob(chunksRef.current, {
          type: mimeType || 'audio/webm',
        });
        chunksRef.current = [];
        mediaRecorderRef.current = null;

        handleAudioBlob(blob);
      };

      recorder.onerror = () => {
        stream.getTracks().forEach((t) => t.stop());
        mediaRecorderRef.current = null;
        setMarimbaState('idle');
      };

      mediaRecorderRef.current = recorder;
      setMarimbaState('listening');
      recorder.start();
    } catch {
      // User denied mic or MediaRecorder not available
      setMarimbaState('idle');
    }
  }, [handleAudioBlob]);

  const discardRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      // Remove the onstop handler so it doesn't send the audio
      mediaRecorderRef.current.onstop = () => {
        // Just release the mic tracks without processing
        mediaRecorderRef.current = null;
      };
      // Stop all tracks to release mic
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
      mediaRecorderRef.current.stop();
    }
    chunksRef.current = [];
    mediaRecorderRef.current = null;
    setMarimbaState('idle');
    console.log('[Marimba] Recording discarded');
  }, []);

  const toggleListening = useCallback(() => {
    if (marimbaState === 'listening') {
      stopRecording();
    } else if (marimbaState === 'idle') {
      startRecording();
    }
    // While thinking or speaking, tapping mic is a no-op
  }, [marimbaState, startRecording, stopRecording]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state !== 'inactive') {
        mediaRecorderRef.current?.stop();
      }
      audioRef.current?.pause();
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    };
  }, []);

  return { marimbaState, toggleListening, discardRecording, isSupported, lastResponse };
}
