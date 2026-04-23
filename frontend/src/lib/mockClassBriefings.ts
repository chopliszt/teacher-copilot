/**
 * Mock class briefings — prototype only.
 *
 * In production this is assembled from live connectors:
 *   Google Sheets → student list, count, emails
 *   Toddle        → current unit, recent submissions, flags
 *   History DB    → last session notes, what was covered
 *
 * Replace with: GET /api/class/:group/briefing  once connectors are live.
 */

export interface ClassBriefing {
  group: string;
  subject: string;
  studentCount: number;
  flags: number;                // absences, missing work, urgent notes
  marimbaNote: string;
  unit: string;                 // current unit/topic
  lastSession: string;          // what happened last time
  sources: ('Toddle' | 'Google Sheets' | 'Internal')[];
}

export const MOCK_CLASS_BRIEFINGS: Record<string, ClassBriefing> = {
  '8A1': {
    group: '8A1',
    subject: 'Digital Design',
    studentCount: 22,
    flags: 1,
    unit: 'Unit 3 — Typography & Layout',
    lastSession: 'Finished mood boards. Most groups are ready to move into grid layout.',
    marimbaNote:
      'One flag: Sofía M. has 2 missing assignments. ' +
      'The rest of the group is on track. Good moment to intro grid systems today.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '9A1': {
    group: '9A1',
    subject: 'Diseño Digital',
    studentCount: 18,
    flags: 0,
    unit: 'Unit 4 — AI & Design',
    lastSession: 'Prompt engineering intro — students tested Midjourney and ChatGPT for concept ideation. Surprisingly good results from the quieter students.',
    marimbaNote:
      'No flags. Energy was high last time — good momentum to build on. ' +
      'Consider a quick share-out before jumping into today\'s activity.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '9A2': {
    group: '9A2',
    subject: 'Homeroom',
    studentCount: 22,
    flags: 0,
    unit: 'Homeroom',
    lastSession: 'Weekly check-in. Two students mentioned stress about upcoming exams.',
    marimbaNote:
      'Homeroom — no academic content. ' +
      'Quick attendance, any announcements, then let them settle before the day starts.',
    sources: ['Google Sheets'],
  },

  '10A1': {
    group: '10A1',
    subject: 'Diseño Digital',
    studentCount: 20,
    flags: 1,
    unit: 'Unit 5 — Brand Identity',
    lastSession: 'Logo iteration round 2. Most students are converging on a direction. Valentina\'s concept stands out — encourage her to push further.',
    marimbaNote:
      'One flag: CAT 1 submissions close soon — 3 students haven\'t submitted yet. ' +
      'Worth a verbal reminder at the start of class.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '10A2': {
    group: '10A2',
    subject: 'Diseño Digital',
    studentCount: 19,
    flags: 0,
    unit: 'Unit 5 — Brand Identity',
    lastSession: 'Peer critique session. Students gave each other unusually constructive feedback — best group dynamic so far this semester.',
    marimbaNote:
      'No flags, strong group. They respond well to autonomy — try giving them open studio time today.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '5B1': {
    group: '5B1',
    subject: 'Digital Design',
    studentCount: 25,
    flags: 2,
    unit: 'Intro to Creative Tools',
    lastSession: 'Nano Banana game session — students explored cause/effect logic through gameplay. High engagement, especially from students who usually disengage.',
    marimbaNote:
      '2 flags: Pedro L. and Andrés V. still don\'t have Figma access. ' +
      'Worth arriving 5 minutes early to sort it out — otherwise they sit out.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '5B2': {
    group: '5B2',
    subject: 'Digital Design',
    studentCount: 24,
    flags: 0,
    unit: 'Intro to Creative Tools',
    lastSession: 'Nano Banana game session — solid run. This group finished faster than 5B1; they might be ready for the extension challenge next time.',
    marimbaNote:
      'No flags. Ahead of schedule compared to 5B1 — a good problem to have.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '6B1': {
    group: '6B1',
    subject: 'Digital Design',
    studentCount: 23,
    flags: 1,
    unit: 'Unit 2 — Visual Communication',
    lastSession: 'Students created their first digital posters. Strong use of contrast; weak on hierarchy — worth revisiting.',
    marimbaNote:
      'One flag: María G. was absent last two sessions — she\'ll need a quick catch-up.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '6B2': {
    group: '6B2',
    subject: 'Digital Design',
    studentCount: 22,
    flags: 0,
    unit: 'Unit 2 — Visual Communication',
    lastSession: 'Intro to color theory. Students used the color wheel activity well — most understood warm/cool tension.',
    marimbaNote:
      'No flags. Lively group — structure the class tightly or they\'ll drift.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '7A1': {
    group: '7A1',
    subject: 'Digital Design',
    studentCount: 21,
    flags: 0,
    unit: 'Unit 3 — Storytelling',
    lastSession: 'Storyboard workshop. Most groups have a clear narrative arc. One group went abstract — let them run with it.',
    marimbaNote:
      'No flags. Creative and self-directed — minimal intervention needed today.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '7B': {
    group: '7B',
    subject: 'Digital Design',
    studentCount: 24,
    flags: 2,
    unit: 'Unit 3 — Storytelling',
    lastSession: 'Storyboard workshop — slower progress than 7A1. Two groups still don\'t have a clear concept.',
    marimbaNote:
      '2 flags: group pacing and one missing parent signature form. Check in with the two struggling groups first.',
    sources: ['Toddle', 'Google Sheets'],
  },

  '4A': {
    group: '4A',
    subject: 'Digital Design',
    studentCount: 20,
    flags: 0,
    unit: 'Unit 1 — Intro to Design',
    lastSession: 'Drawing with shapes activity. Students discovered Canva for the first time — lots of excitement.',
    marimbaNote:
      'Youngest group. Keep instructions short and visual. They respond well to "show, don\'t tell".',
    sources: ['Toddle', 'Google Sheets'],
  },

  '4B': {
    group: '4B',
    subject: 'Digital Design',
    studentCount: 21,
    flags: 1,
    unit: 'Unit 1 — Intro to Design',
    lastSession: 'Drawing with shapes activity — similar to 4A but this group needed more guidance to stay on task.',
    marimbaNote:
      'One flag: Tomás R. has a known attention challenge — seat him at the front and check in early.',
    sources: ['Toddle', 'Google Sheets'],
  },
};

export const DEFAULT_CLASS_BRIEFING: Omit<ClassBriefing, 'group' | 'subject'> = {
  studentCount: 0,
  flags: 0,
  unit: '—',
  lastSession: 'No session history available yet.',
  marimbaNote: "I'll have more context here once the connectors are live.",
  sources: ['Internal'],
};
