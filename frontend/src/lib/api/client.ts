import axios from 'axios';
import { z } from 'zod';
import { stripEmailMarkdown } from '../parseEmailArtifact';

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
  source: z.enum(['user_task', 'email', 'meeting', 'action_item']).optional(),
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

export async function syncEmails(): Promise<void> {
  const res = await httpClient.post<{ status: string; message?: string }>(
    '/api/emails/sync',
    {},
    { timeout: 60_000 }
  );
  if (res.data.status === 'error') {
    throw new Error(res.data.message ?? 'Gmail sync failed');
  }
}

export interface LastSyncState {
  last_sync_at: string | null;
  emails_found: number;
  status: string;
}

export async function fetchLastSync(): Promise<LastSyncState> {
  const res = await httpClient.get<LastSyncState>('/api/emails/last-sync');
  return res.data;
}

export async function dismissEmail(id: string): Promise<void> {
  await httpClient.delete(`/api/important-emails/${id}`);
}

export async function dismissAllEmails(): Promise<void> {
  await httpClient.delete('/api/important-emails');
}

export const ClassDisruptionSchema = z.object({
  description: z.string(),
  day: z.string(),
  schedule_day: z.coerce.number().nullable(),
  time: z.string().nullable().optional(),
  groups_affected: z.array(z.string()),
});

export const WeeklyScheduleSchema = z.object({
  week_label: z.string(),
  meetings: z.array(z.object({
    description: z.string(),
    day: z.string(),
    schedule_day: z.coerce.number().nullable(),
    time: z.string().nullable().optional(),
    location: z.string().nullable().optional(),
    mandatory: z.boolean().nullable().optional(),
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

export async function fetchGroupSessions(group: string): Promise<ClassSession[]> {
  const response = await httpClient.get(`/api/class/${group}/sessions`);
  return z.array(ClassSessionSchema).parse(response.data);
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
  const response = await httpClient.post('/api/weekly-schedule', { document_text }, { timeout: 90_000 });
  const parsed = WeeklyScheduleSchema.safeParse(response.data);
  if (!parsed.success) {
    console.warn('[WeeklySchedule] Zod mismatch:', parsed.error.issues);
    return response.data as WeeklySchedule;
  }
  return parsed.data;
}

export async function clearWeeklySchedule(): Promise<void> {
  await httpClient.delete('/api/weekly-schedule');
}

// ── Task chat ───────────────────────────────────────────────────────────────

export const EmailDetailSchema = z.object({
  id: z.string(),
  subject: z.string(),
  sender: z.string(),
  snippet: z.string(),
  body: z.string(),
  date: z.string(),
  category: z.string(),
  thread_id: z.string(),
  rfc822_message_id: z.string(),
  // Clean email addresses that were on the original Cc line. Empty array
  // when the email had no CC, or when it predates the cc column and the
  // lazy backfill hasn't run yet (will populate on first chat open).
  cc: z.array(z.string()).default([]),
});

export type EmailDetail = z.infer<typeof EmailDetailSchema>;

export async function fetchEmailDetail(id: string): Promise<EmailDetail> {
  const response = await httpClient.get(`/api/important-emails/${id}`);
  return EmailDetailSchema.parse(response.data);
}

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
  // Only present on assistant messages produced by the backend — describes
  // any Gmail tool calls Marimba made to answer that turn. The backend
  // ignores this field if it shows up in inbound history.
  tool_calls?: ChatToolCall[];
}

export interface ChatToolMatch {
  id: string;
  subject: string;
  from: string;
  date: string;
}

export interface ChatToolCall {
  name: string;
  args: Record<string, unknown>;
  result_count?: number | null;
  matches?: ChatToolMatch[];
  error?: string;
}

export interface ChatTurnResponse {
  reply: string;
  tool_calls?: ChatToolCall[];
}

export async function chatWithTask(payload: {
  task_id: string;
  source: string;
  title: string;
  messages: ChatMessage[];
}): Promise<ChatTurnResponse> {
  const response = await httpClient.post('/api/chat/task', payload, { timeout: 120_000 });
  const data = response.data as { reply?: string; tool_calls?: ChatToolCall[] };
  return {
    reply: data.reply ?? '',
    tool_calls: data.tool_calls ?? [],
  };
}

export interface DraftReplyResult {
  to: string;
  subject: string;
  body: string;
  // Addresses that were on the original Cc line — the composer surfaces
  // these as opt-in chips. Empty when the original had no CC.
  original_cc: string[];
}

export async function draftEmailReply(
  emailId: string,
  messages: ChatMessage[],
): Promise<DraftReplyResult> {
  const response = await httpClient.post(
    `/api/emails/${emailId}/draft-reply`,
    { messages },
    { timeout: 60_000 },
  );
  const data = response.data as {
    to: string;
    subject: string;
    body: string;
    original_cc?: string[];
  };
  // Mistral occasionally leaks markdown into the body — strip it so the draft
  // is plain text by the time it hits the editable preview.
  return {
    to: data.to,
    subject: data.subject,
    body: stripEmailMarkdown(data.body ?? ''),
    original_cc: data.original_cc ?? [],
  };
}

export async function sendEmailReply(
  emailId: string,
  payload: { to: string; subject: string; body: string; cc?: string },
): Promise<{ sent: boolean }> {
  const response = await httpClient.post(`/api/emails/${emailId}/reply`, payload);
  return response.data as { sent: boolean };
}

export async function saveEmailReplyAsDraft(
  emailId: string,
  payload: { to: string; subject: string; body: string; cc?: string },
): Promise<{ saved: boolean }> {
  const response = await httpClient.post(`/api/emails/${emailId}/save-draft`, payload);
  return response.data as { saved: boolean };
}

export async function saveEmailComposeAsDraft(payload: {
  to?: string;
  subject: string;
  body: string;
  cc?: string;
}): Promise<{ saved: boolean }> {
  const response = await httpClient.post('/api/emails/save-draft', payload);
  return response.data as { saved: boolean };
}

/**
 * Send a freeform email with optional attachments.
 *
 * Uses multipart/form-data because attachments ride along as file uploads.
 * The backend caps total attachment size at 20 MB.
 */
export async function composeEmail(payload: {
  to: string;
  subject: string;
  body: string;
  cc?: string;
  attachments?: File[];
}): Promise<{ sent: boolean; attachment_count: number }> {
  const form = new FormData();
  form.append('to', payload.to);
  form.append('subject', payload.subject);
  form.append('body', payload.body);
  if (payload.cc && payload.cc.trim()) {
    form.append('cc', payload.cc.trim());
  }
  (payload.attachments ?? []).forEach((file) => form.append('attachments', file, file.name));
  const response = await httpClient.post('/api/emails/compose', form, {
    timeout: 120_000,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data as { sent: boolean; attachment_count: number };
}

export const PreferencesSchema = z.object({
  ignore_rules: z.string(),
  personal_context: z.string(),
});

export type Preferences = z.infer<typeof PreferencesSchema>;

export async function fetchPreferences(): Promise<Preferences> {
  const response = await httpClient.get('/api/preferences');
  return PreferencesSchema.parse(response.data);
}

export async function savePreferences(
  payload: { ignore_rules?: string; personal_context?: string },
): Promise<Preferences> {
  const response = await httpClient.put('/api/preferences', payload);
  return PreferencesSchema.parse({
    ignore_rules: response.data.ignore_rules,
    personal_context: response.data.personal_context,
  });
}

export async function recordPriorityFeedback(payload: {
  task_id: string;
  task_title: string;
  source: string;
  priority_level: string;
  rating: 'relevant' | 'noise' | 'skip';
  context_json: string;
}): Promise<void> {
  await httpClient.post('/api/priority-feedback', payload);
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

// ── Student flags ──────────────────────────────────────────────────────────

export interface StudentFlag {
  name: string;
  notes: string;
}

export type StudentFlagsByGroup = Record<string, StudentFlag[]>;

export async function fetchStudentFlags(): Promise<StudentFlagsByGroup> {
  const response = await httpClient.get('/api/student-flags');
  return (response.data as StudentFlagsByGroup) ?? {};
}

// ── Lesson plan ─────────────────────────────────────────────────────────────

export interface LessonContextSnapshot {
  group: string;
  subject: string;
  time_label: string;
  duration_min: number;
  last_sessions: Array<{ date: string; notes: string; what_worked: string }>;
  recent_plans: Array<{ date: string; plan_text: string }>;
}

export interface LessonToolCallSummary {
  name: string;
  args: Record<string, unknown>;
  saved?: boolean;
  group?: string;
  date?: string;
  error?: string;
}

export interface LessonChatResponse {
  reply: string;
  context_snapshot: LessonContextSnapshot;
  tool_calls?: LessonToolCallSummary[];
}

export async function lessonPlanChat(
  group: string,
  messages: ChatMessage[],
): Promise<LessonChatResponse> {
  const response = await httpClient.post(
    `/api/lesson-plan/${encodeURIComponent(group)}/chat`,
    { messages: messages.map((m) => ({ role: m.role, content: m.content })) },
    { timeout: 120_000 },
  );
  return response.data as LessonChatResponse;
}

export async function lessonPlanAssignment(
  group: string,
  planText: string,
): Promise<{ reply: string }> {
  const response = await httpClient.post(
    `/api/lesson-plan/${encodeURIComponent(group)}/assignment`,
    { plan_text: planText },
    { timeout: 90_000 },
  );
  return response.data as { reply: string };
}

export interface SavedLessonPlan {
  id: string;
  group: string;
  date: string;
  created_at: string;
}

export async function saveLessonPlan(
  group: string,
  payload: {
    date: string;
    plan_text: string;
    context_snapshot?: LessonContextSnapshot | null;
    chosen_option?: number | null;
  },
): Promise<SavedLessonPlan> {
  const response = await httpClient.post(
    `/api/lesson-plan/${encodeURIComponent(group)}/save`,
    payload,
  );
  return response.data as SavedLessonPlan;
}

export interface RecentLessonPlan {
  id: string;
  group: string;
  date: string;
  plan_text: string;
  chosen_option: number | null;
  created_at: string;
}

export async function fetchRecentLessonPlans(
  group: string,
  limit = 3,
): Promise<RecentLessonPlan[]> {
  const response = await httpClient.get(
    `/api/lesson-plan/${encodeURIComponent(group)}/recent`,
    { params: { limit } },
  );
  return response.data as RecentLessonPlan[];
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
