import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { fetchImportantEmails, fetchLastSync, syncEmails, dismissEmail, dismissAllEmails, type ImportantEmail, type LastSyncState } from '../api/client';

export function useImportantEmails() {
  return useQuery<ImportantEmail[], Error>({
    queryKey: ['important-emails'],
    queryFn: fetchImportantEmails,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLastSync() {
  return useQuery<LastSyncState, Error>({
    queryKey: ['last-sync'],
    queryFn: fetchLastSync,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useSyncEmails() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: syncEmails,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['important-emails'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
      queryClient.invalidateQueries({ queryKey: ['last-sync'] });
    },
    onError: (err: Error) => {
      const msg = err.message.toLowerCase();
      if (msg.includes('not configured')) {
        toast.warning('Gmail not connected — run auth_gmail.py to set up', {
          id: 'gmail-unconfigured',
          duration: 8000,
        });
      } else if (msg.includes('expired') || msg.includes('revoked')) {
        toast.error('Gmail token expired — re-run auth_gmail.py in the backend', {
          id: 'gmail-token-expired',
          duration: 0, // stays until dismissed
        });
      } else {
        toast.error('Email sync failed', {
          description: err.message,
          duration: 8000,
        });
      }
    },
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
