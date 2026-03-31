/**
 * commands.ts — Shared command implementations for both platforms.
 *
 * Each command returns a response object:
 *   { text, buttons?, file? }
 *
 * Platform adapters translate these into native API calls.
 */

import api from './api';
import { registry } from './connectors/registry';
import { getSession, clearSession, setMode, setPlan } from './sessions';
import { listRecordings, transcribeAudio } from './audio-transcript';

// ── Types ─────────────────────────────────────────────────────────

export interface Button {
  label: string;
  callbackData: string;
}

export interface BotResponse {
  text: string;
  buttons?: Button[][];
  file?: { path: string; name: string };
}

// ── Response helpers ──────────────────────────────────────────────

function text(t: string): BotResponse {
  return { text: t };
}

function menu(t: string, buttons: Button[][]): BotResponse {
  return { text: t, buttons };
}

// ── Menu commands ─────────────────────────────────────────────────

function cmdMenu(): BotResponse {
  return menu('*Main Control Center*\nSelect a category:', [
    [{ label: '📊 Monitoring', callbackData: 'menu:cat:monitoring' }],
    [{ label: '📝 Plans & AI', callbackData: 'menu:cat:plans' }],
    [{ label: '⚙️ System', callbackData: 'menu:cat:system' }],
  ]);
}

function cmdSubmenuMonitoring(): BotResponse {
  return menu('📊 *Monitoring*\nReal-time War-Room insights:', [
    [{ label: '📊 Dashboard', callbackData: 'cmd:dashboard' }],
    [{ label: '📈 Progress', callbackData: 'cmd:progress' }],
    [{ label: '💻 Status', callbackData: 'cmd:status' }],
    [{ label: '💬 Compact View', callbackData: 'cmd:compact' }],
    [{ label: '⚠️ Errors', callbackData: 'cmd:errors' }],
    [{ label: '⬅️ Back', callbackData: 'menu:main' }],
  ]);
}

function cmdSubmenuPlans(): BotResponse {
  return menu('📝 *Plans & AI*\nDraft, view, edit, and launch plans:', [
    [{ label: '✨ Draft New Plan', callbackData: 'cmd:draft_prompt' }],
    [{ label: '🎙 Transcribe Recording', callbackData: 'cmd:transcribe' }],
    [{ label: '👁 View Plan', callbackData: 'cmd:viewplan' }],
    [{ label: '✏️ Edit Plan', callbackData: 'cmd:edit' }],
    [{ label: '🚀 Launch Plan', callbackData: 'cmd:startplan' }],
    [{ label: '📂 All Plans', callbackData: 'menu:plans' }],
    [{ label: '⬅️ Back', callbackData: 'menu:main' }],
  ]);
}

function cmdSubmenuSystem(): BotResponse {
  return menu('⚙️ *System*\nSystem operations & resources:', [
    [{ label: '📈 Token Usage', callbackData: 'cmd:usage' }],
    [{ label: '🧠 Skills', callbackData: 'cmd:skills' }],
    [{ label: '🔔 Notifications', callbackData: 'cmd:preferences' }],
    [{ label: '⬅️ Back', callbackData: 'menu:main' }],
  ]);
}

// ── Monitoring commands ───────────────────────────────────────────

async function cmdDashboard(): Promise<BotResponse> {
  const { rooms, summary } = await api.getRooms();
  const total = summary.total || 0;
  const active = (summary.pending || 0) + (summary.engineering || 0) + (summary.qa_review || 0) + (summary.fixing || 0);
  const passed = summary.passed || 0;
  const failed = summary.failed_final || 0;

  const makeBar = (count: number, t: number, len = 12): string => {
    if (t === 0) return '░'.repeat(len);
    const filled = Math.round((count / t) * len);
    return '█'.repeat(filled) + '░'.repeat(len - filled);
  };

  const pctPass = total ? (passed / total * 100).toFixed(1) : '0.0';
  const pctFail = total ? (failed / total * 100).toFixed(1) : '0.0';
  const pctAct = total ? (active / total * 100).toFixed(1) : '0.0';

  return text(`🎛 *OS TWIN COMMAND CENTER* 🎛
_System Status:_ 🟢 *ONLINE*

📊 *WAR-ROOMS OVERVIEW*
\`─────────────────────────────\`
🏃‍♂️ *Active:*   \`${String(active).padEnd(4)}\`
✅ *Passed:*   \`${String(passed).padEnd(4)}\`
❌ *Failed:*   \`${String(failed).padEnd(4)}\`
📦 *Total:*    \`${String(total).padEnd(4)}\`
\`─────────────────────────────\`

📈 *EXECUTION PROGRESS*
✅ \`Passed:\` \`${makeBar(passed, total)}\` \`${pctPass.padStart(5)}%\`
❌ \`Failed:\` \`${makeBar(failed, total)}\` \`${pctFail.padStart(5)}%\`
��‍♂️ \`Active:\` \`${makeBar(active, total)}\` \`${pctAct.padStart(5)}%\``);
}

async function cmdStatus(): Promise<BotResponse> {
  const { rooms, error } = await api.getRooms();
  if (error) return text(`⚠️ ${error}`);
  if (!rooms.length) return text('ℹ️ No War-Rooms found.');

  const emoji: Record<string, string> = { passed: '✅', running: '🏃‍♂️', engineering: '🏃‍♂️', pending: '⏳', 'qa-review': '👀', review: '👀', fixing: '🔧', 'failed-final': '❌' };
  const lines = ['📋 *War-Rooms Status:*', '`─────────────────────────────`'];
  for (const r of rooms) {
    const e = r.status.includes('fail') ? '❌' : (emoji[r.status] || '❓');
    lines.push(`${e} \`${r.room_id}\` : ${r.status.toUpperCase()} \`[${r.message_count} msgs]\``);
  }
  lines.push('`─────────────────────────────`');
  return text(lines.join('\n'));
}

async function cmdCompact(): Promise<BotResponse> {
  const { rooms, error } = await api.getRooms();
  if (error) return text(`⚠️ ${error}`);
  const active = rooms.filter(r => !['passed', 'failed-final'].includes(r.status));
  if (!active.length) return text('ℹ️ No active agents right now.');

  const lines = ['💬 *Latest Agent Messages:*'];
  for (const r of active.slice(0, 8)) {
    const ch = await api.getRoomChannel(r.room_id, 1);
    const msgs = ch?.messages || ch || [];
    if (Array.isArray(msgs) && msgs.length) {
      const m = msgs[0];
      let body = (m.body || '').slice(0, 100).replace(/\n/g, ' ');
      body = body.replace(/[*_`]/g, '');
      lines.push(`*${r.room_id}* (${m.from || 'Unknown'}): \`${body}...\``);
    }
  }
  return text(lines.length === 1 ? 'ℹ️ No active agents right now.' : lines.join('\n'));
}

async function cmdErrors(): Promise<BotResponse> {
  const { rooms, error } = await api.getRooms();
  if (error) return text(`⚠️ ${error}`);
  const failed = rooms.filter(r => r.status.includes('fail'));
  if (!failed.length) return text('✅ System is stable. No active errors.');

  const lines: string[] = [];
  for (const r of failed) {
    lines.push(`⚠️ *${r.room_id}* is ${r.status.toUpperCase()}`);
    const ch = await api.getRoomChannel(r.room_id, 3);
    const msgs = ch?.messages || ch || [];
    if (Array.isArray(msgs)) {
      for (const m of [...msgs].reverse()) {
        if (['fail', 'error'].includes(m.type)) {
          const body = (m.body || '').slice(0, 150).replace(/\n/g, ' ').replace(/[*_`]/g, '');
          lines.push(`  └ ❌ \`${body}...\``);
          break;
        }
      }
    }
  }
  return text(lines.join('\n'));
}

// ── Plan commands ─────────────────────────────────────────────────

async function cmdPlans(): Promise<BotResponse> {
  const { plans, error } = await api.getPlans();
  if (error) return text(`⚠️ ${error}`);
  if (!plans.length) return text('ℹ️ No plans found.');

  const lines = ['📂 *Project Plans:*'];
  for (const p of plans) {
    let title = p.title || 'Untitled';
    if (title.length > 40) title = title.slice(0, 37) + '...';
    lines.push(`• *${title}* (${p.status || 'unknown'})\n  └ \`ID: ${p.plan_id}\``);
  }
  return text(lines.join('\n'));
}

async function cmdSkills(): Promise<BotResponse> {
  const skills = await api.getSkills();
  if (!skills.length) return text('ℹ️ No skills installed.');
  const lines = ['🧠 *Available Skills:*'];
  for (const s of skills.slice(0, 50)) {
    const tags = (s.tags && s.tags.length) ? s.tags.join(', ') : 'General';
    lines.push(`• \`${s.name}\`: [${tags}]`);
  }
  return text(lines.join('\n'));
}

async function cmdUsage(): Promise<BotResponse> {
  const stats = await api.getStats();
  if (stats?._error) return text(`⚠️ ${stats._error}`);

  const completion = stats?.completion_rate?.value ?? 0;
  const epics = stats?.active_epics?.value ?? 0;
  const plans = stats?.total_plans?.value ?? 0;
  const escalations = stats?.escalations_pending?.value ?? 0;

  return text(`📈 *STATS REPORT*
\`─────────────────────────────\`
📋 *Total Plans:*      \`${plans}\`
🏃‍♂️ *Active Epics:*     \`${epics}\`
📊 *Completion Rate:*  \`${completion.toFixed(1)}%\`
⚠️ *Escalations:*      \`${escalations}\`
\`─────────────────────────────\``);
}

export function cmdHelp(): BotResponse {
  return text(`*OS Twin Command Center — Help Menu*
\`─────────────────────────────\`

*Interactive AI Agent*
  /menu — Main interactive command menu.
  /draft <idea> — Create a new plan from a text prompt.
  /transcribe — Transcribe a voice recording with AI.
  /edit — Select a plan to edit and refine with AI.
  /startplan — Select and launch a plan.
  /viewplan — Select and read a plan.
  /cancel — Exit current editing/drafting session.

*Monitoring & Insights*
  /dashboard — Visual UI with real-time progress bars.
  /status — Detailed breakdown of every active War-Room.
  /compact — Sneak peek at the latest messages from agents.
  /errors — Extracts the root cause of any failed War-Rooms.

*Project & AI Resources*
  /plans — List all project Plans and their current status.
  /skills — View the library of tools the AI is permitted to use.
  /usage — Stats report.

*System Operations*
  /new — Wipe old War-Room data safely to start fresh.
  /restart — Reboot the Command Center background process.`);
}

// ── System commands ───────────────────────────────────────────────

async function cmdNew(): Promise<BotResponse> {
  const result = await api.shellCommand('rm -rf .war-rooms && mkdir .war-rooms');
  if (result?._error) return text(`❌ Failed to clean War-Rooms: ${result._error}`);
  return text('🧹 *Cleaned up all War-Rooms data.* Ready for a new Plan.');
}

async function cmdRestart(): Promise<BotResponse> {
  const result = await api.stopDashboard();
  if (result?._error) return text(`❌ Failed to restart: ${result._error}`);
  return text('🔄 *Restarting Command Center...*');
}

// ── Plan selection menus ──────────────────────────────────────────

async function _planButtons(prefix: string): Promise<Button[][] | null> {
  const { plans } = await api.getPlans();
  if (!plans.length) return null;
  return plans.slice(0, 10).map(p => {
    let title = p.title || p.plan_id;
    if (title.length > 25) title = title.slice(0, 22) + '...';
    return [{ label: `📄 ${title}`, callbackData: `${prefix}:${p.plan_id}` }];
  });
}

async function cmdViewplanMenu(): Promise<BotResponse> {
  const buttons = await _planButtons('menu:view');
  if (!buttons) return text('ℹ️ No plans found.');
  return menu('👁 *Select a Plan to View:*', buttons);
}

async function cmdEditMenu(): Promise<BotResponse> {
  const buttons = await _planButtons('menu:edit');
  if (!buttons) return text('ℹ️ No plans found. Use /draft <idea> to create one.');
  return menu('✏️ *Select a Plan to Edit:*', buttons);
}

async function cmdStartplanMenu(): Promise<BotResponse> {
  const buttons = await _planButtons('menu:launch_prompt');
  if (!buttons) return text('ℹ️ No plans found. Use /draft <idea> to create one.');
  return menu('🚀 *Select a Plan to Launch:*', buttons);
}

// ── Plan actions ──────────────────────────────────────────────────

async function cmdViewPlan(planId: string): Promise<BotResponse> {
  const data = await api.getPlan(planId);
  if (data?._error) return text(`❌ Plan \`${planId}\` not found.`);
  let content: string = data.content || '';
  if (content.length > 3500) content = content.slice(0, 3500) + '\n...[truncated]';
  return text(`📄 *Plan: ${planId}*\n\`\`\`markdown\n${content}\n\`\`\``);
}

function cmdStartEditing(userId: string, platform: string, planId: string): BotResponse {
  setPlan(userId, platform, planId);
  setMode(userId, platform, 'editing');
  return text(`✏️ *Editing Mode Active for \`${planId}\`*\n\nSend instructions to the AI to refine this plan. Type /cancel to stop editing.`);
}

function cmdPromptLaunch(planId: string): BotResponse {
  return menu(`⚠️ *Confirm Launch*\nAre you sure you want to launch \`${planId}\`? This will wipe the current war-rooms.`, [
    [{ label: '🚀 Launch', callbackData: `menu:launch_confirm:${planId}` }],
    [{ label: '❌ Cancel', callbackData: 'menu:launch_cancel' }],
  ]);
}

async function cmdLaunchPlan(planId: string): Promise<BotResponse[]> {
  const data = await api.getPlan(planId);
  if (data?._error) return [text(`❌ Plan \`${planId}\` not found.`)];
  const result = await api.launchPlan(planId, data.content);
  if (result?._error) return [text(`❌ Failed to launch plan: ${result._error}`)];
  return [text(`🚀 *Plan Launched!* \`${planId}\`\n\nUse /dashboard or /status to monitor progress.`)];
}

// ── AI draft / refine ─────────────────────────────────────────────

async function processDraft(userId: string, platform: string, idea: string): Promise<BotResponse[]> {
  setPlan(userId, platform, 'new');
  setMode(userId, platform, 'drafting');

  const responses: BotResponse[] = [text(`⏳ *Drafting Plan...*\nIdea: \`${idea}\`\nPlease wait while the AI generates the initial plan.`)];

  try {
    const result = await api.refinePlan({ message: `Draft a new plan for: ${idea}` });

    if (result?._error) {
      clearSession(userId, platform);
      responses.push(text(`❌ Failed to draft plan: ${result._error}`));
      return responses;
    }

    const planText = result.plan || result.refined_plan || result.raw_result?.full_response || '';
    const planId = result.raw_result?.plan_id || _generateSlug(idea);

    const created = await api.createPlan({ title: idea, content: planText, workingDir: '.' });

    setMode(userId, platform, 'editing');
    setPlan(userId, platform, created?.plan_id || planId);

    responses.push(text(`✅ *Plan Drafted:* \`${created?.plan_id || planId}\`\n\nYou are now in editing mode. Send further instructions to refine it, or /cancel to exit.`));

    if (planText && planText.length < 3500) {
      responses.push(text(`📄 *Plan Content:*\n\`\`\`markdown\n${planText}\n\`\`\``));
    }

    if (result.explanation) {
      responses.push(text(`📝 *Plan Summary:*\n\n${result.explanation}`));
    }
  } catch (err: any) {
    clearSession(userId, platform);
    responses.push(text(`❌ Failed to draft plan: ${err.message}`));
  }

  return responses;
}

export async function handleStatefulText(userId: string, platform: string, userText: string): Promise<BotResponse[]> {
  const session = getSession(userId, platform);

  if (session.mode === 'awaiting_idea') {
    return processDraft(userId, platform, userText);
  }

  const planId = session.activePlanId;
  if (!planId) {
    clearSession(userId, platform);
    return [];
  }

  const responses: BotResponse[] = [text(`⏳ *Refining \`${planId}\`...*`)];

  try {
    session.chatHistory.push({ role: 'user', content: userText });

    const result = await api.refinePlan({
      message: userText,
      planId,
      chatHistory: session.chatHistory.slice(0, -1),
    });

    if (result?._error) {
      responses.push(text(`❌ Failed to refine plan: ${result._error}`));
      return responses;
    }

    const planText = result.plan || result.refined_plan || '';

    if (planText) {
      await api.savePlan(planId, planText);
    }

    session.chatHistory.push({ role: 'assistant', content: 'I have updated the plan as requested.' });

    responses.push(text(`✅ *Plan Updated:* \`${planId}\``));

    if (planText && planText.length < 3500) {
      responses.push(text(`📄 *Updated Plan:*\n\`\`\`markdown\n${planText}\n\`\`\``));
    }

    if (result.explanation) {
      responses.push(text(`📝 *Changes:*\n\n${result.explanation}\n\n_(Send more instructions to keep editing, or /cancel to exit)_`));
    }
  } catch (err: any) {
    responses.push(text(`❌ Failed to refine plan: ${err.message}`));
  }

  return responses;
}

// ── Audio transcription ───────────────────────────────────────────

async function cmdTranscribe(userId: string, platform: string): Promise<BotResponse[]> {
  const files = listRecordings();
  if (!files.length) return [text('ℹ️ No recordings found. Use `/join` in a voice channel first.')];

  // If multiple recordings, show selection buttons
  if (files.length > 1) {
    const buttons = files.slice(0, 8).map(f => {
      const label = f.length > 30 ? f.slice(0, 27) + '...' : f;
      return [{ label: `🎙 ${label}`, callbackData: `menu:transcribe:${f}` }];
    });
    return [menu('🎙 *Select a recording to transcribe:*', buttons)];
  }

  // Single recording — transcribe directly
  return transcribeFile(userId, platform, files[0]);
}

async function transcribeFile(userId: string, platform: string, filename: string): Promise<BotResponse[]> {
  const responses: BotResponse[] = [text(`⏳ *Transcribing* \`${filename}\`...\nThis may take a moment.`)];

  try {
    const result = await transcribeAudio(filename);
    const mins = Math.floor(result.durationSecs / 60);
    const secs = Math.round(result.durationSecs % 60);

    const session = getSession(userId, platform);
    session.lastTranscription = result.text;
    session.lastActivity = Date.now();

    let transcriptDisplay = result.text;
    if (transcriptDisplay.length > 3000) {
      transcriptDisplay = transcriptDisplay.slice(0, 3000) + '\n...[truncated]';
    }

    responses.push(text(`🎙 *Transcription* (${mins}m ${secs}s)\n\n${transcriptDisplay}`));
    responses.push(menu('What would you like to do with this transcription?', [
      [{ label: '📝 Draft Plan from Recording', callbackData: 'cmd:transcribe_plan' }],
      [{ label: '🔄 Transcribe Another', callbackData: 'cmd:transcribe' }],
    ]));
  } catch (err: any) {
    responses.push(text(`❌ Transcription failed: ${err.message}`));
  }

  return responses;
}

async function cmdTranscribePlan(userId: string, platform: string): Promise<BotResponse[]> {
  const session = getSession(userId, platform);
  if (!session.lastTranscription) {
    return [text('⚠️ No transcription available. Run /transcribe first.')];
  }

  const idea = `Plan based on voice discussion:\n\n${session.lastTranscription}`;
  return processDraft(userId, platform, idea);
}

function _generateSlug(idea: string): string {
  const stopWords = new Set(['a', 'an', 'the', 'build', 'create', 'make', 'write', 'i', 'want', 'to', 'for', 'of', 'some']);
  const words = idea.replace(/[^a-zA-Z0-9\s]/g, '').toLowerCase().split(/\s+/);
  const meaningful = words.filter(w => !stopWords.has(w));
  const slug = (meaningful.length ? meaningful : words).slice(0, 3).join('-');
  const hash = Math.random().toString(16).slice(2, 6);
  return slug ? `${slug}-${hash}` : `plan-${hash}`;
}

// ── Notification & Feedback commands ──────────────────────────────

async function cmdFeedback(userId: string, platform: string, args: string): Promise<BotResponse[]> {
  const idea = args.trim();
  if (!idea) {
    return [text('📝 *Feedback:* Please include your feedback message.\nUsage: `/feedback <your feedback>`')];
  }
  
  // Try to find the latest active room for this user to associate feedback with
  const { rooms } = await api.getRooms();
  const latestRoom = (rooms && rooms[0]?.room_id) || 'global';
  
  try {
    await api.postComment(latestRoom, `${platform}:${userId}`, idea);
    return [text('✅ *Feedback received!* Thank you for your input. It has been posted to the dashboard.')];
  } catch (err: any) {
    return [text(`❌ Failed to post feedback: ${err.message}`)];
  }
}

async function cmdPreferences(userId: string, platform: string): Promise<BotResponse[]> {
  const config = registry.getConfig(platform as any);
  if (!config) return [text('❌ Connector configuration not found.')];

  const prefs = config.notification_preferences || { events: [], enabled: true };
  const status = prefs.enabled ? '🔔 *Enabled*' : '🔕 *Disabled*';
  
  const buttons: Button[][] = [
    [{ 
      label: prefs.enabled ? '🔕 Disable All' : '🔔 Enable All', 
      callbackData: `prefs:toggle_global:${!prefs.enabled}` 
    }],
    [{ label: '🎯 Manage Subscriptions', callbackData: 'cmd:subscriptions' }],
    [{ label: '⬅️ Back', callbackData: 'menu:cat:system' }],
  ];

  return [menu(`⚙️ *Notification Preferences*\n\nStatus: ${status}\n\nYou can toggle global notifications or subscribe to specific events.`, buttons)];
}

async function cmdSubscriptions(userId: string, platform: string): Promise<BotResponse[]> {
  const config = registry.getConfig(platform as any);
  if (!config) return [text('❌ Connector configuration not found.')];

  const prefs = config.notification_preferences || { events: [], enabled: true };
  const events: { id: string; label: string }[] = [
    { id: 'plan_started', label: '🚀 Plan Started' },
    { id: 'epic_passed', label: '✅ EPIC Passed' },
    { id: 'epic_failed', label: '❌ EPIC Failed' },
    { id: 'epic_retry', label: '🔄 EPIC Retry' },
    { id: 'feedback_needed', label: '🤔 Feedback Needed' },
    { id: 'error', label: '⚠️ Errors' },
  ];

  const buttons: Button[][] = events.map(e => {
    const isSubscribed = prefs.events.includes(e.id);
    return [{
      label: `${isSubscribed ? '✅' : '⬜️'} ${e.label}`,
      callbackData: `prefs:toggle_event:${e.id}`
    }];
  });

  buttons.push([{ label: '⬅️ Back', callbackData: 'cmd:preferences' }]);

  return [menu('🎯 *Event Subscriptions*\nSelect which events you want to be notified about:', buttons)];
}

async function cmdProgress(): Promise<BotResponse[]> {
  const { plans } = await api.getPlans();
  const activePlans = plans ? plans.filter(p => p.status !== 'completed' && p.status !== 'failed') : [];
  
  if (activePlans.length === 0) {
    return [text('ℹ️ No active plans found.')];
  }

  const progressLines = activePlans.map(p => {
    const pct = p.pct_complete || 0;
    const bar = '█'.repeat(Math.floor(pct / 10)) + '░'.repeat(10 - Math.floor(pct / 10));
    return `*${p.title || p.plan_id}*\n\`${bar}\` ${pct}%\nStatus: ${p.status}`;
  });

  return [text(`📈 *Current Progress*\n\n${progressLines.join('\n\n')}`)];
}

async function handleToggleGlobal(userId: string, platform: string, enabled: boolean): Promise<BotResponse[]> {
  const config = registry.getConfig(platform as any);
  const prefs = config?.notification_preferences || { events: [], enabled: true };
  await registry.updateConfig(platform as any, {
    notification_preferences: { ...prefs, enabled }
  });
  return cmdPreferences(userId, platform);
}

async function handleToggleEvent(userId: string, platform: string, eventId: string): Promise<BotResponse[]> {
  const config = registry.getConfig(platform as any);
  if (!config) return [];

  const prefs = config.notification_preferences || { events: [], enabled: true };
  let newEvents = [...prefs.events];
  
  if (newEvents.includes(eventId)) {
    newEvents = newEvents.filter(e => e !== eventId);
  } else {
    newEvents.push(eventId);
  }

  await registry.updateConfig(platform as any, {
    notification_preferences: { ...prefs, events: newEvents }
  });
  
  return cmdSubscriptions(userId, platform);
}

// ── Unified router ────────────────────────────────────────────────

export async function routeCommand(userId: string, platform: string, command: string, args = ''): Promise<BotResponse[]> {
  switch (command) {
    case 'menu':        return [cmdMenu()];
    case 'help':
    case 'start':       return [cmdHelp()];
    case 'dashboard':   return [await cmdDashboard()];
    case 'status':      return [await cmdStatus()];
    case 'compact':     return [await cmdCompact()];
    case 'plans':       return [await cmdPlans()];
    case 'errors':      return [await cmdErrors()];
    case 'skills':      return [await cmdSkills()];
    case 'usage':       return [await cmdUsage()];
    case 'new':         return [await cmdNew()];
    case 'restart':     return [await cmdRestart()];
    case 'cancel':
      clearSession(userId, platform);
      return [text('🛑 Action cancelled. Session cleared.')];
    case 'draft': {
      const idea = args.trim();
      if (!idea) {
        setPlan(userId, platform, 'new');
        setMode(userId, platform, 'awaiting_idea');
        return [text('✨ What\'s your idea? Send me a message describing what you want to build:')];
      }
      return processDraft(userId, platform, idea);
    }
    case 'transcribe':  return cmdTranscribe(userId, platform);
    case 'transcribe_plan': return cmdTranscribePlan(userId, platform);
    case 'edit':        return [await cmdEditMenu()];
    case 'startplan':   return [await cmdStartplanMenu()];
    case 'viewplan':    return [await cmdViewplanMenu()];
    case 'feedback':    return await cmdFeedback(userId, platform, args);
    case 'preferences': return await cmdPreferences(userId, platform);
    case 'subscriptions': return await cmdSubscriptions(userId, platform);
    case 'progress':    return await cmdProgress();
    default:            return [text('⚠️ Unknown command. Type /help for a list of commands.')];
  }
}

export async function routeCallback(userId: string, platform: string, callbackData: string): Promise<BotResponse[]> {
  if (callbackData === 'menu:plans')             return [await cmdPlans()];
  if (callbackData === 'menu:cat:monitoring')     return [cmdSubmenuMonitoring()];
  if (callbackData === 'menu:cat:plans')          return [cmdSubmenuPlans()];
  if (callbackData === 'menu:cat:system')         return [cmdSubmenuSystem()];
  if (callbackData === 'menu:main')               return [cmdMenu()];
  if (callbackData === 'menu:launch_cancel')      return [text('🛑 Launch cancelled.')];

  if (callbackData === 'cmd:draft_prompt')
    return [text('✨ Send /draft <your idea> to create a new plan.')];

  if (callbackData.startsWith('cmd:')) {
    const cmd = callbackData.slice(4);
    return routeCommand(userId, platform, cmd);
  }

  if (callbackData.startsWith('menu:transcribe:')) {
    const filename = callbackData.slice('menu:transcribe:'.length);
    return transcribeFile(userId, platform, filename);
  }
  if (callbackData.startsWith('menu:view:')) {
    const planId = callbackData.split(':')[2];
    return [await cmdViewPlan(planId)];
  }
  if (callbackData.startsWith('menu:edit:')) {
    const planId = callbackData.split(':')[2];
    return [cmdStartEditing(userId, platform, planId)];
  }
  if (callbackData.startsWith('menu:launch_prompt:')) {
    const planId = callbackData.split(':')[2];
    return [cmdPromptLaunch(planId)];
  }
  if (callbackData.startsWith('menu:launch_confirm:')) {
    const planId = callbackData.split(':')[2];
    return cmdLaunchPlan(planId);
  }

  if (callbackData.startsWith('prefs:toggle_global:')) {
    const enabled = callbackData.split(':')[2] === 'true';
    return await handleToggleGlobal(userId, platform, enabled);
  }
  if (callbackData.startsWith('prefs:toggle_event:')) {
    const eventId = callbackData.split(':')[2];
    return await handleToggleEvent(userId, platform, eventId);
  }

  return [];
}
