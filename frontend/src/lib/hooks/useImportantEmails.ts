import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchImportantEmails, dismissEmail, dismissAllEmails, type ImportantEmail } from '../api/client';

export function useImportantEmails() {
  return useQuery<ImportantEmail[], Error>({
    queryKey: ['important-emails'],
    queryFn: fetchImportantEmails,
    staleTime: 5 * 60 * 1000,
  });
}

export function useDismissEmail() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: dismissEmail,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['important-emails'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}

export function useDismissAllEmails() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: dismissAllEmails,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['important-emails'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}
