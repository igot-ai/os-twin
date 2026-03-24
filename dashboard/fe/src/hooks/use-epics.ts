import useSWR from 'swr';
import { Epic, Task, DAG, EpicStatus } from '@/types';
import { apiPost, apiPut, apiPatch } from '@/lib/api-client';

export function useEpics(planId: string) {
  const { data, error, mutate, isLoading } = useSWR<Epic[]>(planId ? `/plans/${planId}/epics` : null);

  const createEpic = async (epic: Partial<Epic>) => {
    const newEpic = await apiPost<Epic>(`/plans/${planId}/epics`, epic);
    mutate((epics) => (epics ? [...epics, newEpic] : [newEpic]), false);
    return newEpic;
  };

  const updateEpicState = async (ref: string, lifecycle_state: string, status: EpicStatus) => {
    if (!data) return;

    const optimisticEpics = data.map(e => 
      e.epic_ref === ref ? { ...e, lifecycle_state, status } as Epic : e
    );

    mutate(optimisticEpics, false);

    try {
      const updatedEpic = await apiPost<Epic>(`/plans/${planId}/epics/${ref}/state`, {
        lifecycle_state,
        status,
      });
      mutate((epics) => epics?.map(e => e.epic_ref === ref ? updatedEpic : e), false);
      return updatedEpic;
    } catch (err) {
      mutate(); // rollback
      throw err;
    }
  };

  return {
    epics: data,
    isLoading,
    isError: error,
    createEpic,
    updateEpicState,
    refresh: mutate,
  };
}

export function useEpic(planId: string, ref: string) {
  const { data, error, mutate, isLoading } = useSWR<Epic>(
    planId && ref ? `/plans/${planId}/epics/${ref}` : null
  );

  const updateEpic = async (updates: Partial<Epic>) => {
    const updatedEpic = await apiPut<Epic>(`/plans/${planId}/epics/${ref}`, updates);
    mutate(updatedEpic, false);
    return updatedEpic;
  };

  const addTask = async (task: Partial<Task>) => {
    const newTask = await apiPost<Task>(`/plans/${planId}/epics/${ref}/tasks`, task);
    mutate((epic) => epic ? { ...epic, tasks: [...(epic.tasks || []), newTask] } : epic, false);
    return newTask;
  };

  const updateTask = async (taskId: string, updates: Partial<Task>) => {
    if (!data) return;

    const updatedTasks = (data.tasks || []).map(t => 
      t.task_id === taskId ? { ...t, ...updates } : t
    );
    const optimisticEpic = { ...data, tasks: updatedTasks };

    mutate(optimisticEpic, false);

    try {
      const updatedEpic = await apiPatch<Epic>(`/plans/${planId}/epics/${ref}/tasks`, { taskId, ...updates });
      mutate(updatedEpic, false);
      return updatedEpic;
    } catch (err) {
      mutate(); // rollback
      throw err;
    }
  };

  const updateTaskOrder = async (taskIds: string[]) => {
    const updatedEpic = await apiPut<Epic>(`/plans/${planId}/epics/${ref}/tasks/reorder`, { taskIds });
    mutate(updatedEpic, false);
    return updatedEpic;
  };

  const updateState = async (lifecycle_state: string, status: EpicStatus) => {
    const updatedEpic = await apiPost<Epic>(`/plans/${planId}/epics/${ref}/state`, {
      lifecycle_state,
      status,
    });
    mutate(updatedEpic, false);
    return updatedEpic;
  };

  return {
    epic: data,
    isLoading,
    isError: error,
    updateEpic,
    addTask,
    updateTask,
    updateTaskOrder,
    updateState,
    refresh: mutate,
  };
}

export function useDAG(planId: string) {
  const { data, error, mutate, isLoading } = useSWR<DAG>(
    planId ? `/plans/${planId}/dag` : null
  );

  return {
    dag: data,
    isLoading,
    isError: error,
    refresh: mutate,
  };
}
