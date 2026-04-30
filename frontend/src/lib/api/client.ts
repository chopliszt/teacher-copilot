import axios from 'axios';
import { z } from 'zod';

// Empty string → relative URLs, which Vite proxy (dev) and nginx (prod) both handle.
// Set VITE_API_URL only if you need to hit a remote backend directly.
const BASE_URL = (import.meta.env.VITE_API_URL as string) || '';

const httpClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
});

// ── Zod schemas ────────────────────────────────────────────────────────────

export const PriorityLevelSchema = z.enum(['high', 'medium', 'low']);

export const PriorityItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  priority: PriorityLevelSchema,
  estimated_time: z.string(),
  due_date: z.string(),
  class: z.string(),
  subject: z.string(),
  marimba_note: z.string().nullable().optional(),
});

export const PrioritiesResponseSchema = z.object({
  priorities: z.array(PriorityItemSchema),
  generated_at: z.string(),
  count: z.number(),
});

export const SchedulePeriodSchema = z.object({
  time: z.string(),
  subject: z.string(),
  room: z.string().nullable(),
  group: z.string(),
});

export const ScheduleDaySchema = z.object({
  day: z.number(),
  periods: z.array(SchedulePeriodSchema),
});

export const ScheduleResponseSchema = z.object({
  school: z.string(),
  teacher: z.string(),
  semester: z.string(),
  homeroom: z.object({
    time: z.string(),
    room: z.string(),
    group: z.string(),
    days: z.array(z.number()),
  }),
  classes: z.array(ScheduleDaySchema),
  break: z.string(),
  lunch: z.string(),
  current_day: z.number(),
});

// ── Inferred types ──────────────────────────────────────────────────────────

export type PriorityLevel = z.infer<typeof PriorityLevelSchema>;
export type PriorityItem = z.infer<typeof PriorityItemSchema>;
export type PrioritiesResponse = z.infer<typeof PrioritiesResponseSchema>;
export type SchedulePeriod = z.infer<typeof SchedulePeriodSchema>;
export type ScheduleDay = z.infer<typeof ScheduleDaySchema>;
export type ScheduleResponse = z.infer<typeof ScheduleResponseSchema>;

// ── API functions ────────────────────────────────────────────────────────────

export async function fetchPriorities(): Promise<PrioritiesResponse> {
  const response = await httpClient.get('/api/priorities');
  try {
    return PrioritiesResponseSchema.parse(response.data);
  } catch (zodErr) {
    console.error('[Priorities] Unexpected response shape from /api/priorities:', response.data, zodErr);
    throw new Error(
      `Backend returned unexpected data — check that the server is up to date.\n\nRaw: ${JSON.stringify(response.data, null, 2)}`,
    );
  }
}

export async function fetchSchedule(): Promise<ScheduleResponse> {
  const response = await httpClient.get('/api/schedule');
  return ScheduleResponseSchema.parse(response.data);
}

export const AbsenceSchema = z.object({
  id: z.string(),
  student_name: z.string(),
  group_name: z.string(),
  date: z.string(),
});

export const ImportantEmailSchema = z.object({
  id: z.string(),
  subject: z.string(),
  sender: z.string(),
  snippet: z.string(),
  date: z.string(),
});

export type Absence = z.infer<typeof AbsenceSchema>;
export type ImportantEmail = z.infer<typeof ImportantEmailSchema>;

export async function fetchAbsences(): Promise<Absence[]> {
  const response = await httpClient.get('/api/absences');
  return z.array(AbsenceSchema).parse(response.data);
}

export async function fetchImportantEmails(): Promise<ImportantEmail[]> {
  const response = await httpClient.get('/api/important-emails');
  return z.array(ImportantEmailSchema).parse(response.data);
}

export const ClassDisruptionSchema = z.object({
  description: z.string(),
  day: z.string(),
  schedule_day: z.number().nullable(),
  time: z.string(),
  groups_affected: z.array(z.string()),
});

export const WeeklyScheduleSchema = z.object({
  week_label: z.string(),
  meetings: z.array(z.object({
    description: z.string(),
    day: z.string(),
    schedule_day: z.number().nullable(),
    time: z.string(),
    location: z.string().nullable().optional(),
    mandatory: z.boolean().optional(),
  })),
  class_disruptions: z.array(ClassDisruptionSchema),
  action_items: z.array(z.string()),
  upcoming_dates: z.array(z.object({
    date: z.string(),
    description: z.string(),
  })),
  absences: z.array(z.unknown()),
});

export type ClassDisruption = z.infer<typeof ClassDisruptionSchema>;
export type WeeklySchedule = z.infer<typeof WeeklyScheduleSchema>;

export async function fetchWeeklySchedule(): Promise<WeeklySchedule> {
  const response = await httpClient.get('/api/weekly-schedule');
  return WeeklyScheduleSchema.parse(response.data);
}

export const ClassSessionSchema = z.object({
  id: z.string(),
  group: z.string(),
  date: z.string(),
  schedule_day: z.number(),
  notes: z.string(),
  what_worked: z.string().nullable(),
  created_at: z.string(),
});

export type ClassSession = z.infer<typeof ClassSessionSchema>;

export async function logClassSession(
  group: string,
  body: { notes: string; what_worked?: string },
): Promise<ClassSession> {
  const response = await httpClient.post(`/api/class/${group}/session`, body);
  return ClassSessionSchema.parse(response.data);
}

export async function fetchLastSession(group: string): Promise<ClassSession | null> {
  const response = await httpClient.get(`/api/class/${group}/last-session`);
  if (response.data === null) return null;
  return ClassSessionSchema.parse(response.data);
}

export const UserTaskSchema = z.object({
  id: z.string(),
  title: z.string(),
  priority: z.enum(['high', 'medium', 'low']),
  due_date: z.string().nullable(),
  created_at: z.string(),
});

export type UserTask = z.infer<typeof UserTaskSchema>;

export async function fetchUserTasks(): Promise<UserTask[]> {
  const response = await httpClient.get('/api/tasks');
  return z.array(UserTaskSchema).parse(response.data);
}

export async function addUserTask(body: {
  title: string;
  priority?: string;
  due_date?: string;
}): Promise<UserTask> {
  const response = await httpClient.post('/api/tasks', body);
  return UserTaskSchema.parse(response.data);
}

export async function deleteUserTask(id: string): Promise<void> {
  await httpClient.delete(`/api/tasks/${id}`);
}

export async function uploadWeeklySchedule(document_text: string): Promise<WeeklySchedule> {
  const response = await httpClient.post('/api/weekly-schedule', { document_text });
  return WeeklyScheduleSchema.parse(response.data);
}

// ── Voice ────────────────────────────────────────────────────────────────────

export const VoiceActionSchema = z.object({
  type: z.enum(['open_class', 'add_task', 'open_priority', 'close_all', 'start_meeting_recording']),
  group: z.string().optional(),
  title: z.string().optional(),
  priority: z.enum(['high', 'medium', 'low']).optional(),
  id: z.string().optional(),
});

export const VoiceResponseSchema = z.object({
  text: z.string(),
  audio: z.string().nullable().optional(),   // base64 MP3
  action: VoiceActionSchema.nullable().optional(),
});

export type VoiceAction = z.infer<typeof VoiceActionSchema>;
export type VoiceResponse = z.infer<typeof VoiceResponseSchema>;

// ── Meetings ─────────────────────────────────────────────────────────────────

export const MeetingDraftSchema = z.object({
  meeting_id: z.string(),
  transcription: z.string(),
  summary: z.string(),
  action_items: z.array(z.string()),
  suggested_subject: z.string(),
  email_body: z.string(),
});

export const MeetingSendResponseSchema = z.object({
  sent: z.boolean(),
  error: z.string().optional(),
});

export type MeetingDraft = z.infer<typeof MeetingDraftSchema>;
export type MeetingSendResponse = z.infer<typeof MeetingSendResponseSchema>;

export async function processMeeting(audioBlob: Blob): Promise<MeetingDraft> {
  const ext = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
  const formData = new FormData();
  formData.append('audio', audioBlob, `meeting.${ext}`);
  const response = await httpClient.post('/api/meetings/process', formData, {
    timeout: 180_000,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return MeetingDraftSchema.parse(response.data);
}

export async function uploadMeetingFile(file: File): Promise<MeetingDraft> {
  const formData = new FormData();
  formData.append('audio', file, file.name);
  const response = await httpClient.post('/api/meetings/process', formData, {
    timeout: 180_000,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return MeetingDraftSchema.parse(response.data);
}

export const EmailRecipientSchema = z.object({
  email: z.string(),
  label: z.string().nullable(),
  use_count: z.number(),
});

export type EmailRecipient = z.infer<typeof EmailRecipientSchema>;

export async function fetchEmailRecipients(): Promise<EmailRecipient[]> {
  const response = await httpClient.get('/api/email-recipients');
  return z.array(EmailRecipientSchema).parse(response.data);
}

export async function sendMeetingEmail(
  meetingId: string,
  payload: { to: string; subject: string; body: string },
): Promise<MeetingSendResponse> {
  const response = await httpClient.post(`/api/meetings/${meetingId}/send-email`, payload);
  return MeetingSendResponseSchema.parse(response.data);
}

export async function callVoice(audioBlob: Blob): Promise<VoiceResponse> {
  const ext = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
  const formData = new FormData();
  formData.append('audio', audioBlob, `recording.${ext}`);
  // Pass FormData directly — axios detects it and sets multipart/form-data + boundary automatically
  const response = await httpClient.post('/api/voice', formData, { 
    timeout: 30_000,
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return VoiceResponseSchema.parse(response.data);
}
