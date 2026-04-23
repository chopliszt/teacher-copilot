import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { addUserTask, deleteUserTask, type UserTask } from '../api/client';

export function useUserTasks() {
  return useQuery<UserTask[], Error>({
    queryKey: ['user-tasks'],
    queryFn: async () => [
      { id: 't1', title: 'Review IB ATLs for ethics in AI', priority: 'high', due_date: null, created_at: new Date().toISOString() },
      { id: 't2', title: 'Hackathon / Contest Prep', priority: 'medium', due_date: null, created_at: new Date().toISOString() }
    ],
    staleTime: Infinity,
  });
}

export function useAddTask() {
  const queryClient = useQueryClient();
  return useMutation<UserTask, Error, { title: string; priority?: string; due_date?: string }>({
    mutationFn: addUserTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: deleteUserTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['priorities'] });
    },
  });
}
