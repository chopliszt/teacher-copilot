import { useQuery } from '@tanstack/react-query';
import { fetchWeeklySchedule, type WeeklySchedule } from '../api/client';

export function useWeeklySchedule() {
  return useQuery<WeeklySchedule, Error>({
    queryKey: ['weekly-schedule'],
    queryFn: fetchWeeklySchedule,
    staleTime: Infinity, // only changes when n8n POSTs a new one
  });
}
