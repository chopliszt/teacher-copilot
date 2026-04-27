import { useQuery } from '@tanstack/react-query';
import { fetchSchedule, type ScheduleResponse } from '../api/client';

const SCHEDULE_QUERY_KEY = ['schedule'] as const;

export function useSchedule() {
  return useQuery<ScheduleResponse, Error>({
    queryKey: SCHEDULE_QUERY_KEY,
    queryFn: fetchSchedule,
    staleTime: Infinity, // schedule doesn't change mid-day
    retry: 2,
  });
}
