import useSWR from 'swr';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api-client';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  last_activity_at: string;
  messages: Message[];
}

export function useConversation(id?: string) {
  const { data, error, mutate, isLoading } = useSWR<Conversation>(
    id ? `/conversations/${id}` : null,
    apiGet
  );

  const sendMessage = async (message: string) => {
    // Optimistic update logic could go here if we want, but for streaming we usually
    // handle it outside or rely on WS. For now, just api call.
    // If id exists, it's appended in command endpoint.
  };

  const rename = async (title: string) => {
    if (!id) return;
    await apiPatch(`/conversations/${id}`, { title });
    mutate((prev) => prev ? { ...prev, title } : prev, false);
  };

  const remove = async () => {
    if (!id) return;
    await apiDelete(`/conversations/${id}`);
    mutate(undefined, false);
  };

  return {
    conversation: data,
    isLoading,
    isError: error,
    sendMessage,
    rename,
    remove,
    mutate,
  };
}
