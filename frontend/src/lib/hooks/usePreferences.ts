import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPreferences, savePreferences, type Preferences } from '../api/client';

export function usePreferences() {
  return useQuery<Preferences, Error>({
    queryKey: ['preferences'],
    queryFn: fetchPreferences,
    staleTime: 60_000,
  });
}

export function useSavePreferences() {
  const queryClient = useQueryClient();
  return useMutation<
    Preferences,
    Error,
    { ignore_rules?: string; personal_context?: string }
  >({
    mutationFn: savePreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}
