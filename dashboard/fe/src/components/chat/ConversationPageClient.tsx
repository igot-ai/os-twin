'use client';

import React, { useEffect, useState } from 'react';
import { useConversation } from '@/hooks/use-conversation';
import { ChatHistory } from './ChatHistory';
import { CommandPrompt } from '@/components/ui/CommandPrompt';
import { useWebSocket } from '@/hooks/use-websocket';

export default function ConversationPageClient({ conversationId }: { conversationId: string }) {
  const { conversation, mutate } = useConversation(conversationId);
  const [prompt, setPrompt] = useState('');
  const [streamingContent, setStreamingContent] = useState('');

  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
  const wsUrl = baseUrl.replace(/^http/, 'ws') + '/ws';
  const { lastMessage } = useWebSocket(wsUrl);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'agent_stream' && lastMessage.conversation_id === conversationId) {
      setStreamingContent((prev) => prev + lastMessage.chunk);
      return;
    }

    if (lastMessage.type === 'command_response' && lastMessage.conversation_id === conversationId) {
      setStreamingContent('');
      mutate();
    }
  }, [conversationId, lastMessage, mutate]);

  const handleSubmitPrompt = async (submittedPrompt: string) => {
    try {
      setPrompt('');
      await fetch(baseUrl + '/command', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'test-key',
        },
        body: JSON.stringify({
          message: submittedPrompt,
          mode: 'auto',
          conversation_id: conversationId,
        }),
      });
      mutate();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="flex flex-col h-full relative">
      <div className="h-14 border-b border-[var(--color-border)] flex items-center px-6 shrink-0 bg-[var(--color-surface)]">
        <h1 className="text-sm font-bold text-[var(--color-text-main)] truncate max-w-xl">
          {conversation?.title || 'Loading...'}
        </h1>
      </div>

      <ChatHistory conversationId={conversationId} streamingMessage={streamingContent || undefined} />

      <div className="p-6 shrink-0 bg-[var(--color-background)]">
        <div className="max-w-4xl mx-auto w-full">
          <CommandPrompt
            value={prompt}
            onChange={setPrompt}
            onSubmit={handleSubmitPrompt}
            isConversationActive={true}
          />
        </div>
      </div>
    </div>
  );
}
