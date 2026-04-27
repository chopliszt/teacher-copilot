import { useQuery } from '@tanstack/react-query';
import { fetchPriorities, type PrioritiesResponse } from '../api/client';

const PRIORITIES_QUERY_KEY = ['priorities'] as const;
const FIFTEEN_MINUTES_MS = 15 * 60 * 1_000;

export function usePriorities() {
  return useQuery<PrioritiesResponse, Error>({
    queryKey: PRIORITIES_QUERY_KEY,
    queryFn: fetchPriorities,
    staleTime: FIFTEEN_MINUTES_MS,
    refetchInterval: FIFTEEN_MINUTES_MS,
    retry: 2,
  });
}
