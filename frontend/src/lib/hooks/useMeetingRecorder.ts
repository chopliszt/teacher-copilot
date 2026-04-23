import axios from 'axios';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  processMeeting,
  sendMeetingEmail,
  uploadMeetingFile,
  type MeetingDraft,
} from '../api/client';

function extractErrorMessage(err: unknown, fallback: string): string {
  // FastAPI HTTPException — has response.data.detail (string)
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;

    // Timeout: Axios sets code = 'ECONNABORTED'
    if (err.code === 'ECONNABORTED') {
      return 'La solicitud tardó demasiado. El servidor puede estar ocupado — el archivo está guardado en Downloads, intenta subirlo de nuevo.';
    }

    // Network error (no response at all — proxy dropped, server down, CORS)
    if (!err.response) {
      return `Error de red: no se recibió respuesta del servidor. ${err.message ?? ''}`.trim();
    }

    // Server error with a non-string detail (FastAPI validation array)
    if (detail) return JSON.stringify(detail);
  }

  // Non-Axios error (Zod parse, etc.)
  if (err instanceof Error) return `${err.name}: ${err.message}`;

  return fallback;
}

export type MeetingRecorderState =
  | 'idle'
  | 'recording'
  | 'processing'
  | 'review'
  | 'composing'
  | 'sending'
  | 'done'
  | 'error';

interface UseMeetingRecorderReturn {
  state: MeetingRecorderState;
  recordingSeconds: number;
  draft: MeetingDraft | null;
  meetingId: string | null;
  errorMessage: string | null;
  savedFilename: string | null;
  startRecording: () => Promise<void>;
  stopAndProcess: () => void;
  discardRecording: () => void;
  uploadFile: (file: File) => Promise<void>;
  proceedToCompose: () => void;
  sendEmail: (to: string, subject: string, body: string) => Promise<void>;
  redownloadSavedRecording: () => void;
  reset: () => void;
}

// ── Audio format detection ─────────────────────────────────────────────────────
// Reuses the same priority order as useVoice.ts

function getSupportedMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
  ];
  for (const type of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return '';
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export function useMeetingRecorder(): UseMeetingRecorderReturn {
  const [state, setState] = useState<MeetingRecorderState>('idle');
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [draft, setDraft] = useState<MeetingDraft | null>(null);
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [savedFilename, setSavedFilename] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Holds the last recorded blob so the user can re-download it on error
  const savedBlobRef = useRef<Blob | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Saves the audio blob to the browser's Downloads folder immediately.
  // Called before any server request so the recording is never lost even if the
  // backend call fails, the network drops, or the tab is closed mid-upload.
  const saveToDownloads = useCallback((blob: Blob): string => {
    const ts = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
    const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
    const filename = `reunion-${ts}.${ext}`;

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    // Revoke after a brief delay to let the download initialise
    setTimeout(() => URL.revokeObjectURL(url), 10_000);

    return filename;
  }, []);

  const redownloadSavedRecording = useCallback(() => {
    if (savedBlobRef.current) saveToDownloads(savedBlobRef.current);
  }, [saveToDownloads]);

  const handleAudioBlob = useCallback(async (blob: Blob) => {
    if (!blob.size) {
      setState('error');
      setErrorMessage('La grabación estaba vacía. Intenta de nuevo.');
      return;
    }

    // Save to disk FIRST — before any network call — so the recording is never lost
    savedBlobRef.current = blob;
    const filename = saveToDownloads(blob);
    setSavedFilename(filename);

    setState('processing');

    try {
      const result = await processMeeting(blob);
      setDraft(result);
      setMeetingId(result.meeting_id);
      setState('review');
    } catch (err) {
      setState('error');
      setErrorMessage(extractErrorMessage(err, 'No se pudo procesar la grabación.'));
    }
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getSupportedMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

      chunksRef.current = [];
      setRecordingSeconds(0);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        clearTimer();

        const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });
        chunksRef.current = [];
        mediaRecorderRef.current = null;

        handleAudioBlob(blob);
      };

      recorder.onerror = () => {
        stream.getTracks().forEach((t) => t.stop());
        clearTimer();
        mediaRecorderRef.current = null;
        setState('error');
        setErrorMessage('Error con el micrófono. Intenta de nuevo.');
      };

      mediaRecorderRef.current = recorder;
      setState('recording');
      recorder.start();

      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch {
      setState('error');
      setErrorMessage('No se pudo acceder al micrófono.');
    }
  }, [clearTimer, handleAudioBlob]);

  const stopAndProcess = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      // onstop handles the rest
    }
  }, []);

  const discardRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.onstop = () => {
        mediaRecorderRef.current = null;
      };
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
      mediaRecorderRef.current.stop();
    }
    clearTimer();
    chunksRef.current = [];
    mediaRecorderRef.current = null;
    setRecordingSeconds(0);
    setState('idle');
  }, [clearTimer]);

  const uploadFile = useCallback(async (file: File) => {
    setState('processing');

    try {
      const result = await uploadMeetingFile(file);
      setDraft(result);
      setMeetingId(result.meeting_id);
      setState('review');
    } catch (err) {
      setState('error');
      setErrorMessage(extractErrorMessage(err, 'No se pudo procesar el archivo.'));
    }
  }, []);

  const proceedToCompose = useCallback(() => {
    setState('composing');
  }, []);

  const sendEmail = useCallback(
    async (to: string, subject: string, body: string) => {
      if (!meetingId) return;

      setState('sending');

      try {
        const result = await sendMeetingEmail(meetingId, { to, subject, body });
        if (result.sent) {
          setState('done');
        } else {
          setState('error');
          setErrorMessage(result.error ?? 'No se pudo enviar el correo.');
        }
      } catch (err) {
        setState('error');
        setErrorMessage(extractErrorMessage(err, 'Error al enviar el correo. Intenta de nuevo.'));
      }
    },
    [meetingId],
  );

  const reset = useCallback(() => {
    discardRecording();
    setDraft(null);
    setMeetingId(null);
    setErrorMessage(null);
    setSavedFilename(null);
    savedBlobRef.current = null;
    setState('idle');
  }, [discardRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state !== 'inactive') {
        mediaRecorderRef.current?.stop();
      }
      clearTimer();
    };
  }, [clearTimer]);

  return {
    state,
    recordingSeconds,
    draft,
    meetingId,
    errorMessage,
    savedFilename,
    startRecording,
    stopAndProcess,
    discardRecording,
    uploadFile,
    proceedToCompose,
    sendEmail,
    redownloadSavedRecording,
    reset,
  };
}
