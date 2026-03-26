/**
 * agent-bridge.js — Discord ↔ Ostwin Agent Bridge
 *
 * Queries ostwin dashboard APIs for context about plans, war-rooms,
 * and semantic search results, then uses Gemini to synthesize an answer.
 */

const { GoogleGenerativeAI } = require('@google/generative-ai');

const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:9000';
const OSTWIN_API_KEY = process.env.OSTWIN_API_KEY || '';
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || '';

const headers = {};
if (OSTWIN_API_KEY) headers['X-API-Key'] = OSTWIN_API_KEY;

// ── Helpers ─────────────────────────────────────────────────────────

async function fetchJSON(path) {
  try {
    const res = await fetch(`${DASHBOARD_URL}${path}`, { headers });
    if (!res.ok) {
      console.warn(`[BRIDGE] ${path} returned ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn(`[BRIDGE] Failed to fetch ${path}: ${err.message}`);
    return null;
  }
}

// ── Context Gatherers ───────────────────────────────────────────────

async function getPlans() {
  const data = await fetchJSON('/api/plans');
  if (!data?.plans) return 'No plans found.';
  return data.plans.map(p => {
    const pct = p.pct_complete != null ? `${p.pct_complete}%` : p.status;
    return `- **${p.title}** (${p.plan_id}) — ${pct}, ${p.epic_count || 0} epics`;
  }).join('\n');
}

async function getRooms() {
  const data = await fetchJSON('/api/rooms');
  if (!data?.rooms?.length) return 'No active war-rooms.';
  return data.rooms.map(r =>
    `- ${r.room_id}: ${r.epic_ref || 'N/A'} — status: ${r.status}`
  ).join('\n');
}

async function getStats() {
  const data = await fetchJSON('/api/stats');
  if (!data) return 'Stats unavailable.';
  return [
    `Plans: ${data.total_plans?.value ?? '?'}`,
    `Active epics: ${data.active_epics?.value ?? '?'}`,
    `Completion: ${data.completion_rate?.value ?? '?'}%`,
    `Escalations: ${data.escalations_pending?.value ?? 0}`,
  ].join(' | ');
}

async function semanticSearch(query) {
  const data = await fetchJSON(`/api/search?q=${encodeURIComponent(query)}&limit=5`);
  if (!data?.results?.length) return 'No relevant messages found.';
  return data.results.map(r =>
    `[${r.room_id || 'global'}] ${r.from || '?'} → ${r.type || '?'}: ${(r.body || '').slice(0, 200)}`
  ).join('\n');
}

// ── Main ────────────────────────────────────────────────────────────

/**
 * Ask the ostwin agent a question.
 * @param {string} question — the user's message (minus the @mention).
 * @returns {Promise<string>} the agent's answer.
 */
async function askAgent(question) {
  if (!GOOGLE_API_KEY) {
    return '❌ `GOOGLE_API_KEY` is not set in the bot environment.';
  }

  // 1. Gather context in parallel
  const [plans, rooms, stats, search] = await Promise.all([
    getPlans(),
    getRooms(),
    getStats(),
    semanticSearch(question),
  ]);

  // 2. Build the prompt
  const systemPrompt = `You are OS Twin Assistant, a helpful AI that answers questions about ongoing software projects managed by the Ostwin multi-agent war-room orchestrator.

You have access to the current state of all plans, war-rooms, and message history. Use the context below to answer the user's question accurately and concisely. If you don't have enough information, say so.

Format your response for Discord (markdown, but no triple backtick code blocks over 2000 chars). Keep it concise — aim for 1-3 paragraphs max.`;

  const contextBlock = `## Current Plans
${plans}

## Active War-Rooms
${rooms}

## Stats Overview
${stats}

## Relevant Messages (semantic search for "${question}")
${search}`;

  // 3. Call Gemini
  const geminiModel = process.env.GEMINI_MODEL || 'gemini-2.0-flash';
  const genAI = new GoogleGenerativeAI(GOOGLE_API_KEY);
  const model = genAI.getGenerativeModel({ model: geminiModel });

  try {
    const result = await model.generateContent({
      contents: [
        { role: 'user', parts: [{ text: `${systemPrompt}\n\n---\n\n${contextBlock}\n\n---\n\n**User question:** ${question}` }] },
      ],
    });

    const text = result.response?.text?.();
    if (!text) return '⚠️ Gemini returned an empty response.';

    // Discord message limit is 2000 chars
    return text.length > 1900
      ? text.slice(0, 1900) + '\n\n*…(truncated)*'
      : text;
  } catch (err) {
    console.error('[BRIDGE] Gemini API error:', err.message);
    return '⚠️ Failed to get a response from the AI model. Please try again later.';
  }
}

module.exports = { askAgent };
