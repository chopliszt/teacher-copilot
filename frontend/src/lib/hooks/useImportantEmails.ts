import { useQuery } from '@tanstack/react-query';
import type { ImportantEmail } from '../api/client';

export function useImportantEmails() {
  return useQuery<ImportantEmail[], Error>({
    queryKey: ['important-emails'],
    queryFn: async () => [
      {
        id: 'e1',
        sender: 'Intel Latin America PR',
        subject: 'Finalizing visitor list for 9C',
        snippet: 'Please send us the final list of students and missing permission slips for tomorrow...',
        date: new Date().toISOString()
      },
      {
        id: 'e2',
        sender: "Maria (Carlos's Mom)",
        subject: 'Re: Urgent - Special needs arrangement for Intel visit',
        snippet: 'Yes, I received the slip. Carlos is very excited. What accommodations will he have?',
        date: new Date().toISOString()
      }
    ],
    staleTime: Infinity,
  });
}
