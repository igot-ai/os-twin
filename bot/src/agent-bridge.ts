/**
 * agent-bridge.ts — AI Q&A using dashboard context + Gemini.
 *
 * Shared by both bots for @mention (Discord) or free-text Q&A (Telegram).
 */

import { GoogleGenerativeAI } from '@google/generative-ai';
import config from './config';
import api from './api';

export async function askAgent(question: string): Promise<string> {
  if (!config.GOOGLE_API_KEY) {
    return '❌ `GOOGLE_API_KEY` is not set in the bot environment.';
  }

  // Gather context in parallel
  const [plansData, roomsData, stats, search] = await Promise.all([
    api.getPlans(),
    api.getRooms(),
    api.getStats(),
    api.semanticSearch(question),
  ]);

  const plansText = plansData.plans.length
    ? plansData.plans.map(p => {
        const pct = p.pct_complete != null ? `${p.pct_complete}%` : p.status;
        return `- **${p.title}** (${p.plan_id}) — ${pct}, ${p.epic_count || 0} epics`;
      }).join('\n')
    : 'No plans found.';

  const roomsText = roomsData.rooms.length
    ? roomsData.rooms.map(r => `- ${r.room_id}: ${r.epic_ref || 'N/A'} — status: ${r.status}`).join('\n')
    : 'No active war-rooms.';

  const statsAny = stats as any;
  const statsText = statsAny?._error
    ? 'Stats unavailable.'
    : [
        `Plans: ${stats?.total_plans?.value ?? '?'}`,
        `Active epics: ${stats?.active_epics?.value ?? '?'}`,
        `Completion: ${stats?.completion_rate?.value ?? '?'}%`,
        `Escalations: ${stats?.escalations_pending?.value ?? 0}`,
      ].join(' | ');

  const searchResults = search?.results || search || [];
  const searchText = Array.isArray(searchResults) && searchResults.length
    ? searchResults.map((r: any) => `[${r.room_id || 'global'}] ${r.from || '?'}: ${(r.body || '').slice(0, 200)}`).join('\n')
    : 'No relevant messages found.';

  const systemPrompt = `You are OS Twin Assistant, a helpful AI that answers questions about ongoing software projects managed by the Ostwin multi-agent war-room orchestrator.

Use the context below to answer the user's question accurately and concisely. If you don't have enough information, say so.

Format your response for chat (markdown). Keep it concise — 1-3 paragraphs max.`;

  const contextBlock = `## Current Plans\n${plansText}\n\n## Active War-Rooms\n${roomsText}\n\n## Stats Overview\n${statsText}\n\n## Relevant Messages (semantic search for "${question}")\n${searchText}`;

  try {
    const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
    const model = genAI.getGenerativeModel({ model: config.GEMINI_MODEL });

    const result = await model.generateContent({
      contents: [
        { role: 'user', parts: [{ text: `${systemPrompt}\n\n---\n\n${contextBlock}\n\n---\n\n**User question:** ${question}` }] },
      ],
    });

    const answer = result.response?.text?.();
    if (!answer) return '⚠️ AI returned an empty response.';

    return answer.length > 1900
      ? answer.slice(0, 1900) + '\n\n*…(truncated)*'
      : answer;
  } catch (err: any) {
    console.error('[BRIDGE] AI API error:', err.message);
    return '⚠️ Failed to get a response from the AI model.';
  }
}
