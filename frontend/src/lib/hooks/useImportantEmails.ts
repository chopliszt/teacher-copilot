import { useQuery } from '@tanstack/react-query';
import { fetchImportantEmails, type ImportantEmail } from '../api/client';

export function useImportantEmails() {
  return useQuery<ImportantEmail[], Error>({
    queryKey: ['important-emails'],
    queryFn: fetchImportantEmails,
    staleTime: 5 * 60 * 1000,
  });
}
