/**
 * Mock briefings — prototype only.
 *
 * In production each briefing is assembled by the backend from live connectors:
 *   Toddle  → grades, assignments, submission lists
 *   Gmail   → email threads, auto-drafted replies
 *   Google Sheets → student lists, attendance, passwords
 *
 * Replace with: GET /api/task/:id/briefing  once connectors are live.
 */

export type ActionType = 'grading' | 'review' | 'attendance' | 'email-draft' | 'generic';

export interface TaskBriefing {
  marimbaNote: string;
  source: string;
  actionType: ActionType;
  primaryActionLabel: string;
  draft?: string;
  progress?: { done: number; total: number; label: string };
  previewRows?: string[];
  overflowLabel?: string;
}

export const MOCK_BRIEFINGS: Record<string, TaskBriefing> = {
  urgent_1: {
    marimbaNote:
      '9A2 submitted 18 projects in Toddle. Nothing graded yet. ' +
      'Homeroom is in 10 minutes — a good moment to let them know feedback is coming today.',
    source: 'Toddle',
    actionType: 'grading',
    primaryActionLabel: 'Open in Toddle',
    progress: { done: 0, total: 18, label: 'graded' },
    previewRows: ['Sofia M.', 'Carlos A.', 'Valeria R.'],
    overflowLabel: '+ 15 more',
  },

  urgent_2: {
    marimbaNote:
      'Mrs. Rodriguez wants to discuss Juan\'s recent performance. ' +
      'Your 8A1 class starts at 7:50 — a quick reply sets the tone before you see him.',
    source: 'Gmail',
    actionType: 'email-draft',
    primaryActionLabel: 'Send reply',
    draft:
      'Dear Mrs. Rodriguez,\n\n' +
      'Thank you for reaching out. I would love to connect and discuss Juan\'s progress.\n\n' +
      'Would Thursday at 3:30pm work for you? In the meantime, I\'ll keep a close eye on him in class.\n\n' +
      'Warm regards',
  },

  important_1: {
    marimbaNote:
      '10A1 is not on today\'s schedule — you have room to breathe. ' +
      'I suggest opening with a real case study before moving to hands-on exercises.',
    source: 'Internal',
    actionType: 'generic',
    primaryActionLabel: 'Open lesson template',
  },

  important_2: {
    marimbaNote:
      'No class tied to this today. Best handled during lunch (12:10pm). ' +
      'Last inventory was logged 3 weeks ago.',
    source: 'Google Sheets',
    actionType: 'generic',
    primaryActionLabel: 'Open inventory sheet',
  },

  routine_1: {
    marimbaNote:
      '9A2 homeroom starts in 10 minutes. 22 students expected. ' +
      'Mark attendance here and it will sync to the student system.',
    source: 'Google Sheets',
    actionType: 'attendance',
    primaryActionLabel: 'Mark all present',
    progress: { done: 0, total: 22, label: 'marked present' },
    previewRows: ['Sofia M.', 'Carlos A.', 'Valeria R.', 'Ana L.', 'Miguel S.'],
    overflowLabel: '+ 17 more',
  },

  routine_2: {
    marimbaNote:
      '5B1 is at 1:30pm — plenty of time. ' +
      '12 of 22 students submitted yesterday. The rest will likely hand it in at the start of class.',
    source: 'Toddle',
    actionType: 'review',
    primaryActionLabel: 'Open in Toddle',
    progress: { done: 12, total: 22, label: 'submitted' },
    previewRows: ['Andrés V. — missing', 'Pedro L. — missing', 'María C. — missing'],
    overflowLabel: '+ 7 more missing',
  },
};

export const DEFAULT_BRIEFING: TaskBriefing = {
  marimbaNote: "Here's what you need to handle. I'll have more context once the connectors are live.",
  source: 'Internal',
  actionType: 'generic',
  primaryActionLabel: 'Mark done',
};
