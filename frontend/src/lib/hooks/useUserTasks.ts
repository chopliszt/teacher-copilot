import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchUserTasks, addUserTask, deleteUserTask, type UserTask } from '../api/client';

export function useUserTasks() {
  return useQuery<UserTask[], Error>({
    queryKey: ['user-tasks'],
    queryFn: fetchUserTasks,
    staleTime: 0,
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
