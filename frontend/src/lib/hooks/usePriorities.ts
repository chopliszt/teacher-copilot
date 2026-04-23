import { useQuery } from '@tanstack/react-query';
import type { PrioritiesResponse } from '../api/client';

export function usePriorities() {
  return useQuery<PrioritiesResponse, Error>({
    queryKey: ['priorities'],
    queryFn: async () => ({
      count: 3,
      generated_at: new Date().toISOString(),
      priorities: [
        {
          id: '1',
          title: 'Urgent: Permission missing for Tech Visit',
          priority: 'high',
          estimated_time: '5m',
          due_date: 'Today',
          class: '9C Homeroom',
          subject: 'Admin',
          marimba_note: "A parent just emailed about Carlos's missing permission slip for the Intel Costa Rica visit tomorrow. I've drafted a quick reply with the digital link attached."
        },
        {
          id: '2',
          title: 'Prep IB Project Review',
          priority: 'medium',
          estimated_time: '15m',
          due_date: 'Today, 11:30 AM',
          class: 'Grade 10',
          subject: 'Digital Design',
          marimba_note: "You have Grade 10 next at 11:30. Let's review the 3 pending AI ethics project proposals before they arrive. I've summarized them for you."
        },
        {
          id: '3',
          title: 'Finish Teacher AI Talk',
          priority: 'low',
          estimated_time: '30m',
          due_date: 'Tomorrow',
          class: 'AI Committee',
          subject: 'Faculty Training',
          marimba_note: "Your presentation 'Prompting for Educators' is tomorrow afternoon. You still need to finish the slide on accommodating Special Needs students with AI."
        }
      ]
    }),
    staleTime: Infinity,
  });
}
