export interface FormattedDueDate {
  label: string;
  isOverdue: boolean;
  isDueToday: boolean;
}

export function formatDueDate(dueDateStr?: string | null): FormattedDueDate {
  if (!dueDateStr) {
    return { label: '', isOverdue: false, isDueToday: false };
  }

  const dueDate = new Date(dueDateStr);
  if (isNaN(dueDate.getTime())) {
    return { label: '', isOverdue: false, isDueToday: false };
  }

  const today = new Date();

  // Normalize both dates to start of day for accurate day-diff
  today.setHours(0, 0, 0, 0);
  dueDate.setHours(0, 0, 0, 0);

  const diffMs = dueDate.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1_000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return { label: 'Overdue', isOverdue: true, isDueToday: false };
  }
  if (diffDays === 0) {
    return { label: 'Due today', isOverdue: false, isDueToday: true };
  }
  if (diffDays === 1) {
    return { label: 'Tomorrow', isOverdue: false, isDueToday: false };
  }

  const label = dueDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  return { label, isOverdue: false, isDueToday: false };
}

export function getTimeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function formatTodayLabel(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

/** Maps JS getDay() (0=Sun) to the backend's 1-6 rotation (1=Mon…5=Fri, 6=weekend) */
export function getCurrentScheduleDay(): number {
  const jsDay = new Date().getDay(); // 0=Sun, 1=Mon, …, 6=Sat
  if (jsDay === 0 || jsDay === 6) return 6; // weekend → day 6
  return jsDay; // Mon=1, Tue=2, Wed=3, Thu=4, Fri=5
}
