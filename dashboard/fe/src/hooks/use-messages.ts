import useSWR from 'swr';
import { ChannelMessage } from '@/types';
import { apiPost } from '@/lib/api-client';

export function useMessages(planId: string, epicRef: string) {
  const isMockRealtime = process.env.NEXT_PUBLIC_ENABLE_MOCK_REALTIME === 'true';
  const { data, error, mutate, isLoading } = useSWR<ChannelMessage[]>(
    planId && epicRef ? `/plans/${planId}/epics/${epicRef}/messages` : null,
    {
      refreshInterval: isMockRealtime ? 10000 : 0,
    }
  );

  const sendMessage = async (message: Partial<ChannelMessage>) => {
    const newMessage = await apiPost<ChannelMessage>(
      `/plans/${planId}/epics/${epicRef}/messages`,
      message
    );
    mutate((messages) => (messages ? [...messages, newMessage] : [newMessage]), false);
    return newMessage;
  };

  return {
    messages: data,
    isLoading,
    isError: error,
    sendMessage,
    refresh: mutate,
  };
}
