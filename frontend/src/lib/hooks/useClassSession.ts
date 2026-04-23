import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchLastSession, logClassSession, type ClassSession } from '../api/client';

export function useLastSession(group: string) {
  return useQuery<ClassSession | null, Error>({
    queryKey: ['last-session', group],
    queryFn: () => fetchLastSession(group),
    staleTime: 0, // always fresh after a log
  });
}

export function useLogSession(group: string) {
  const queryClient = useQueryClient();
  return useMutation<ClassSession, Error, { notes: string; what_worked?: string }>({
    mutationFn: (body) => logClassSession(group, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['last-session', group] });
    },
  });
}
