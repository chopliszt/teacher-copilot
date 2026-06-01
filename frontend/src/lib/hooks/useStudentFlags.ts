import { useQuery } from '@tanstack/react-query';
import { fetchStudentFlags, type StudentFlagsByGroup } from '../api/client';

/**
 * Loads the full per-group map of students who need academic support.
 * Cached for 30 min — the file is updated manually so doesn't need to
 * refresh aggressively.
 */
export function useStudentFlags() {
  return useQuery<StudentFlagsByGroup, Error>({
    queryKey: ['student-flags'],
    queryFn: fetchStudentFlags,
    staleTime: 30 * 60 * 1000,
  });
}
