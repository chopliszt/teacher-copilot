import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchEvents,
  fetchUpcomingEvents,
  dismissEvent,
  type EventsResponse,
  type UpcomingEventsResponse,
} from '../api/client';

// Today's (or a given day's) calendar events that earned a place on the
// timeline. Keyed by date so each day caches separately.
export function useEvents(date: string) {
  return useQuery<EventsResponse, Error>({
    queryKey: ['events', date],
    queryFn: () => fetchEvents(date),
    staleTime: 60_000,
  });
}

// The "Coming up" peek — shown events in the next `days` days (after today).
// Keyed under ['events', …] so a dismiss invalidates it too.
export function useUpcomingEvents(after: string, days: number) {
  return useQuery<UpcomingEventsResponse, Error>({
    queryKey: ['events', 'upcoming', after, days],
    queryFn: () => fetchUpcomingEvents(after, days),
    staleTime: 60_000,
  });
}

// The quiet × — soft-dismiss an event. Invalidate the whole 'events' family so
// both today's timeline and "Coming up" refresh immediately (ADHD: visible
// feedback, no stale clutter).
export function useDismissEvent() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: dismissEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}
