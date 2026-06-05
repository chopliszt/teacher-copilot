import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchEvents, dismissEvent, type EventsResponse } from '../api/client';

// Today's (or a given day's) calendar events that earned a place on the
// timeline. Keyed by date so each day caches separately.
export function useEvents(date: string) {
  return useQuery<EventsResponse, Error>({
    queryKey: ['events', date],
    queryFn: () => fetchEvents(date),
    staleTime: 60_000,
  });
}

// The quiet × — soft-dismiss an event. We invalidate the day's events so the
// chip disappears immediately (ADHD: visible feedback, no stale clutter).
export function useDismissEvent(date: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: dismissEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events', date] });
    },
  });
}
