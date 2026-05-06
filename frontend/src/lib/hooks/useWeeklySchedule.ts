import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchWeeklySchedule, clearWeeklySchedule, type WeeklySchedule } from '../api/client';

export function useWeeklySchedule() {
  return useQuery<WeeklySchedule, Error>({
    queryKey: ['weekly-schedule'],
    queryFn: fetchWeeklySchedule,
    staleTime: Infinity,
  });
}

export function useClearWeeklySchedule() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: clearWeeklySchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['weekly-schedule'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}
