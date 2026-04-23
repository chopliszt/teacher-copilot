import { useQuery } from '@tanstack/react-query';
import { fetchAbsences, type Absence } from '../api/client';

export function useAbsences() {
  return useQuery<Absence[], Error>({
    queryKey: ['absences'],
    queryFn: fetchAbsences,
    staleTime: 5 * 60 * 1000,
  });
}
