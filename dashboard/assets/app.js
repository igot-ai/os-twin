/**
 * OS Twin Command Center — Real-time SSE Client
 * TASK-003 + TASK-004: SSE client, DOM wiring, animations, integration
 */

'use strict';

// ── Theme Management ────────────────────────────────────────────────────────

let currentTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', currentTheme);

function initTheme() {
  const icon = document.getElementById('theme-icon');
  if (icon) icon.innerText = currentTheme === 'dark' ? '🌙' : '☀️';
}

function toggleTheme() {
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  localStorage.setItem('theme', currentTheme);
  const icon = document.getElementById('theme-icon');
  if (icon) icon.innerText = currentTheme === 'dark' ? '🌙' : '☀️';
}

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_COLOR = {
  pending:        '#555',
  engineering:    '#00d4ff',
  'qa-review':    '#ffd93d',
  fixing:         '#ff9f43',
  passed:         '#00ff88',
  'failed-final': '#ff6b6b',
  paused:         '#ffd93d',
};

const STATUS_LABEL = {
  pending:        'PENDING',
  engineering:    'ENGINEERING',
  'qa-review':    'QA REVIEW',
  fixing:         'FIXING',
  passed:         'PASSED',
  'failed-final': 'FAILED',
  paused:         'PAUSED',
};

const MSG_ICON = {
  task: '📋', done: '✓', review: '🔍', pass: '✅',
  fail: '✗', fix: '🔧', signoff: '✍', release: '🚀', error: '⚠',
};

const PROGRESS_PCT = {
  pending: 5, engineering: 35, 'qa-review': 65,
  fixing: 45, passed: 100, 'failed-final': 100, paused: 50,
};

const TEMPLATES = {
  hello: `# Plan: Hello World

## Config
working_dir: .

## Epic: EPIC-001 — Hello module with tests

Build hello.py with a greet() function and full pytest test suite.

Acceptance criteria:
- greet("World") returns "Hello, World!"
- Module is importable
- pytest passes with 3+ assertions
`,

  api: `# Plan: REST API

## Config
working_dir: .

## Epic: EPIC-001 — API foundation

Create FastAPI app with health endpoint, Pydantic models, and CRUD endpoints for items.

Acceptance criteria:
- GET /health returns {"status":"ok"}
- POST /items creates item, GET /items lists all
- Pydantic validation on all inputs

## Epic: EPIC-002 — Test suite

Write pytest tests for all endpoints with full coverage.

Acceptance criteria:
- All endpoints tested
- 90%+ coverage
`,

  fullstack: `# Plan: Full-Stack App

## Config
working_dir: .

## Epic: EPIC-001 — Backend API

FastAPI backend with SQLite, auth, and CRUD endpoints.

Acceptance criteria:
- Auth flow works end-to-end
- All CRUD endpoints functional

## Epic: EPIC-002 — Frontend SPA

React SPA with login, data views, and API integration.

Acceptance criteria:
- Login/logout works
- Data views render from API

## Epic: EPIC-003 — Deployment

Docker compose for frontend + backend, GitHub Actions CI pipeline.

Acceptance criteria:
- docker compose up runs the full stack
- CI runs lint, test, build
`,
};

// ── State ──────────────────────────────────────────────────────────────────

let rooms = {};
let allMessages = [];
let channelFilter = null;
let socket = null;
let reconnectMs = 1000;
let releaseExpanded = false;
let planHistory = [];
let activePlanId = null;

// ── Boot ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  loadConfig();
  loadPlanHistory();
  loadInitialState().then(() => connect());
  pollManagerStatus();
  setInterval(pollManagerStatus, 3000);
});

// ── SSE ────────────────────────────────────────────────────────────────────

function connect() {
  if (socket) socket.close();

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/ws`;
  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    reconnectMs = 1000;
    setConn(true);
    // Initial ping to verify bidirectional link
    socket.send(JSON.stringify({ type: 'ping' }));
  };

  socket.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'pong') {
        return;
      }
      dispatch(data);
    }
    catch (err) { console.error('WebSocket parse error', err); }
  };

  socket.onclose = () => {
    setConn(false);
    socket = null;
    setTimeout(connect, reconnectMs);
    reconnectMs = Math.min(reconnectMs * 2, 30000);
  };

  socket.onerror = () => {
    socket.close();
  };
}

function dispatch(ev) {
  switch (ev.event) {
    case 'room_created':
      rooms[ev.room.room_id] = ev.room;
      renderCard(ev.room, true);
      updateSummary();
      pushMsg(ev.room.room_id, {
        type: 'task', from_: 'manager', to: 'engineer',
        ref: ev.room.task_ref,
        body: `War-room opened: ${ev.room.room_id}`,
        ts: ev.room.last_activity,
      });
      break;

    case 'room_updated': {
      const prev = rooms[ev.room.room_id];
      rooms[ev.room.room_id] = ev.room;
      renderCard(ev.room, false, prev);
      if (channelFilter === ev.room.room_id) {
        renderRoomDetail(ev.room);
        renderActivityLog(ev.room.room_id);
      }
      updateSummary();
      updateEpicStatuses();
      (ev.new_messages || []).forEach(m => pushMsg(ev.room.room_id, m));
      break;
    }

    case 'room_removed':
      delete rooms[ev.room_id];
      removeCard(ev.room_id);
      updateSummary();
      break;

    case 'release':
      showRelease(ev.content);
      break;

    case 'reaction_toggled':
      // Engagement update (real-time)
      console.log('Reaction toggled:', ev);
      if (typeof updateEngagementUI === 'function') {
        updateEngagementUI(ev.entity_id, ev.state);
      }
      break;

    case 'comment_published':
      // Engagement update (real-time)
      console.log('Comment published:', ev);
      if (typeof updateEngagementUI === 'function') {
        updateEngagementUI(ev.entity_id, ev.state);
      }
      break;
      console.log('Comment published:', ev);
      break;
  }
}

// ── View Management ────────────────────────────────────────────────────────

let currentView = 'grid';

window.setView = function(view) {
  currentView = view;
  const btnGrid = document.getElementById('btn-grid');
  const btnMatrix = document.getElementById('btn-matrix');
  if (btnGrid) btnGrid.classList.toggle('active', view === 'grid');
  if (btnMatrix) btnMatrix.classList.toggle('active', view === 'matrix');

  const grid = document.getElementById('room-grid');
  const matrix = document.getElementById('goal-matrix');
  if (grid) grid.style.display = view === 'grid' ? 'grid' : 'none';
  if (matrix) matrix.style.display = view === 'matrix' ? 'block' : 'none';

  if (view === 'matrix') renderGoalMatrix();
};

function renderGoalMatrix() {
  const head = document.getElementById('matrix-head');
  const body = document.getElementById('matrix-body');
  if (!head || !body) return;

  const roomList = Object.values(rooms);
  if (roomList.length === 0) {
    body.innerHTML = '<tr><td colspan="100" style="text-align:center; padding: 40px; color: var(--text-dim)">No active rooms</td></tr>';
    return;
  }

  // Collect all unique goal names across all rooms
  const allGoals = new Set();
  roomList.forEach(r => {
    if (r.task_description) {
      const tasks = r.task_description.match(/- \[[ xX\-\!]+\] .+/g) || [];
      tasks.forEach(t => allGoals.add(t.replace(/- \[[ xX\-\!]+\] /, '')));
    }
  });

  const goalArray = Array.from(allGoals);

  // Render header
  head.innerHTML = '<th>Goal / Room</th>' + roomList.map(r => `<th>${esc(r.room_id)}</th>`).join('');

  // Render body
  body.innerHTML = goalArray.map(goal => {
    return `<tr>
      <td style="font-weight: 500">${esc(goal)}</td>
      ${roomList.map(r => {
        let status = '';
        if (r.task_description) {
          const lines = r.task_description.split('\n');
          const taskLine = lines.find(line => line.includes(goal) && line.trim().startsWith('- ['));
          if (taskLine) {
            if (taskLine.includes('[x]') || taskLine.includes('[X]')) {
              status = '<span class="cell-passed">✓</span>';
            } else if (taskLine.includes('[-]') || taskLine.includes('[!]')) {
              status = '<span class="cell-failed">✗</span>';
            } else {
              status = '<span class="cell-pending">○</span>';
            }
          }
        }
        return `<td class="matrix-cell">${status}</td>`;
      }).join('')}
    </tr>`;
  }).join('');
}

function renderCard(room, isNew = false, prev = null) {
  const grid = document.getElementById('room-grid');
  if (!grid) return;

  // Remove empty-state placeholder
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  let card = document.getElementById(`room-${room.room_id}`);
  const creating = !card;

  if (creating) {
    card = document.createElement('div');
    card.className = 'room-card';
    card.id = `room-${room.room_id}`;
    card.addEventListener('click', () => selectRoom(room.room_id));
    grid.appendChild(card);
    if (isNew) card.classList.add('anim-slide-up');
  }

  const color = STATUS_COLOR[room.status] || '#555';
  const label = STATUS_LABEL[room.status] || room.status.toUpperCase();
  const pct = PROGRESS_PCT[room.status] ?? 0;
  const isActive = ['engineering', 'qa-review', 'fixing'].includes(room.status);
  const goalPct = room.goal_total > 0 ? Math.round((room.goal_done / room.goal_total) * 100) : 0;

  card.dataset.status = room.status;
  card.style.setProperty('--status-color', color);

  card.innerHTML = `
    <div class="rc-head">
      <span class="rc-id">${room.room_id}</span>
      <span class="rc-chip ${isActive ? 'chip-pulse' : ''}"
            style="color:${color};border-color:${color}40">${label}</span>
    </div>
    <div class="rc-ref">${esc(room.task_ref)}</div>
    <div class="rc-desc">${esc(trunc(room.task_description || '', 90))}</div>
    
    <div class="rc-goal-stats" style="display: flex; justify-content: space-between; font-size: 8px; color: var(--text-dim); margin-bottom: 4px;">
      <span>GOALS: ${room.goal_done}/${room.goal_total}</span>
      <span>${goalPct}%</span>
    </div>

    <div class="rc-bar-wrap">
      <div class="rc-bar" style="width:${pct}%;background:${color}${isActive ? ';animation:barPulse 1.5s ease-in-out infinite' : ''}"></div>
    </div>
    <div class="rc-foot">
      <span style="color:var(--text-dim)">⬡ ${room.message_count}</span>
      ${room.retries > 0 ? `<span style="color:#ff9f43">↻${room.retries}</span>` : ''}
      <span style="color:var(--text-dim)">${fmtTime(room.last_activity)}</span>
    </div>
  `;

  // Border glow
  if (room.status === 'passed') {
    card.style.borderColor = color;
    card.style.boxShadow = `0 0 18px ${color}44, 0 0 36px ${color}18`;
  } else if (isActive) {
    card.style.borderColor = `${color}66`;
    card.style.boxShadow = `0 0 10px ${color}22`;
  } else if (room.status === 'failed-final') {
    card.style.borderColor = `${color}66`;
    card.style.boxShadow = `0 0 10px ${color}22`;
  } else {
    card.style.borderColor = '';
    card.style.boxShadow = '';
  }

  // Flash on status change
  if (!creating && prev && prev.status !== room.status) {
    card.style.animation = 'none';
    void card.offsetWidth; // force reflow
    card.style.animation = 'statusFlash 0.4s ease-out';
  }

  // Selected highlight
  card.classList.toggle('selected', channelFilter === room.room_id);
}

function removeCard(roomId) {
  const card = document.getElementById(`room-${roomId}`);
  if (!card) return;
  card.style.animation = 'fadeOut 0.3s ease-out forwards';
  setTimeout(() => {
    card.remove();
    if (!document.querySelector('.room-card')) restoreEmptyState();
  }, 320);
}

function restoreEmptyState() {
  const grid = document.getElementById('room-grid');
  if (!grid) return;
  const div = document.createElement('div');
  div.id = 'empty-state';
  div.className = 'empty-state';
  div.innerHTML = '<div class="empty-hex">⬡</div><p>No war-rooms active.</p><p class="empty-sub">Launch a plan to get started.</p>';
  grid.appendChild(div);
}

// ── Room Selection ─────────────────────────────────────────────────────────

function selectRoom(roomId) {
  channelFilter = channelFilter === roomId ? null : roomId;
  document.querySelectorAll('.room-card').forEach(c => {
    c.classList.toggle('selected', c.id === `room-${channelFilter}`);
  });

  const detail = document.getElementById('room-detail');
  if (detail) {
    if (channelFilter && rooms[channelFilter]) {
      renderRoomDetail(rooms[channelFilter]);
      detail.style.display = 'block';
    } else {
      detail.style.display = 'none';
    }
  }

  const title = document.getElementById('panel-right-title');
  if (title) title.textContent = channelFilter ? `▸ ${channelFilter}` : '▸ CHANNEL FEED';
  reloadFeed();
}

window.roomAction = async function(action) {
  if (!channelFilter) return;
  const roomId = channelFilter;

  try {
    const res = await fetch(`/api/rooms/${roomId}/action?action=${action}`, { method: 'POST' });
    if (res.ok) {
      console.log(`Room ${roomId} ${action} successful`);
    }
  } catch (e) {
    console.error(`Failed to ${action} room:`, e);
  }
};

function renderRoomDetail(room) {
  setTxt('detail-room-id', room.room_id);
  setTxt('detail-task-ref', room.task_ref);

  const pct = PROGRESS_PCT[room.status] ?? 0;
  const color = STATUS_COLOR[room.status] || '#555';
  const bar = document.getElementById('detail-bar');
  if (bar) {
    bar.style.width = `${pct}%`;
    bar.style.background = color;
  }

  // Update action buttons
  const startBtn = document.getElementById('btn-start-room');
  const pauseBtn = document.getElementById('btn-pause-room');
  const stopBtn = document.getElementById('btn-stop-room');

  if (startBtn) {
    startBtn.style.display = (room.status === 'paused' || room.status === 'failed-final') ? 'inline-block' : 'none';
  }

  if (pauseBtn) {
    if (room.status === 'paused') {
      pauseBtn.textContent = 'resume';
      pauseBtn.onclick = () => roomAction('resume');
      pauseBtn.style.display = 'inline-block';
    } else {
      pauseBtn.textContent = 'pause';
      pauseBtn.onclick = () => roomAction('pause');
      pauseBtn.style.display = ['engineering', 'qa-review', 'fixing'].includes(room.status) ? 'inline-block' : 'none';
    }
  }

  if (stopBtn) {
    stopBtn.style.display = ['engineering', 'qa-review', 'fixing', 'paused', 'pending'].includes(room.status) ? 'inline-block' : 'none';
  }

  // Parse task description for goals
  const list = document.getElementById('detail-goal-list');
  if (list && room.task_description) {
     const tasks = room.task_description.match(/- \[[ xX\-\!]+\] .+/g) || [];
     list.innerHTML = tasks.map(t => {
        const checked = t.includes('[x]') || t.includes('[X]');
        const failed = t.includes('[-]') || t.includes('[!]');
        const text = t.replace(/- \[[ xX\-\!]+\] /, '');
        let icon = checked ? '✓' : (failed ? '✗' : '');
        let cls = checked ? 'checked' : (failed ? 'failed' : '');
        return `
          <div class="goal-item">
            <span class="goal-checkbox ${cls}">${icon}</span>
            <span class="goal-text">${esc(text)}</span>
          </div>
        `;
     }).join('');
  }

  // Fetch and render activity log
  renderActivityLog(room.room_id);
}

async function renderActivityLog(roomId) {
  const logContainer = document.getElementById('detail-activity-log');
  if (!logContainer) return;

  try {
    const res = await fetch(`/api/notifications?room_id=${roomId}&limit=20`);
    const data = await res.json();
    const logs = data.notifications || [];

    if (logs.length === 0) {
      logContainer.innerHTML = '<div style="padding: 10px; color: var(--text-dim)">No activity recorded.</div>';
      return;
    }

    logContainer.innerHTML = logs.map(entry => {
      const ts = fmtTime(entry.ts);
      const event = entry.event.replace(/_/g, ' ');
      return `
        <div class="activity-item">
          <span class="activity-ts">${ts}</span>
          <span class="activity-event">${event}</span>
        </div>
      `;
    }).reverse().join('');
  } catch (e) {
    console.error('Failed to fetch activity log:', e);
  }
}

async function reloadFeed() {
  const feed = document.getElementById('channel-feed');
  if (!feed) return;
  feed.innerHTML = '';

  if (channelFilter) {
    try {
      const res = await fetch(`/api/rooms/${channelFilter}/channel`);
      const data = await res.json();
      (data.messages || []).forEach(m => appendMsg(channelFilter, m, false));
    } catch (e) { console.error(e); }
  } else {
    allMessages.forEach(({ roomId, msg }) => appendMsg(roomId, msg, false));
  }
  scrollFeed();
}

// ── Channel Feed ───────────────────────────────────────────────────────────

function pushMsg(roomId, msg) {
  allMessages.push({ roomId, msg });
  if (allMessages.length > 600) allMessages.shift();

  if (!channelFilter || channelFilter === roomId) {
    appendMsg(roomId, msg, true);
    scrollFeed();
  }
}

function appendMsg(roomId, msg, animate) {
  const feed = document.getElementById('channel-feed');
  if (!feed) return;

  // Remove "waiting" placeholder
  const placeholder = feed.querySelector('.feed-empty');
  if (placeholder) placeholder.remove();

  const el = document.createElement('div');
  el.className = `feed-msg feed-${msg.type || 'unknown'}`;
  if (animate) el.style.animation = 'fadeIn 0.2s ease-out';

  const icon  = MSG_ICON[msg.type] || '·';
  const from  = msg.from_ || msg.from || '?';
  const to    = msg.to || '?';

  el.innerHTML =
    `<span class="fm-time">${fmtTime(msg.ts)}</span>` +
    `<span class="fm-route">${esc(from)}→${esc(to)}</span>` +
    `<span class="fm-type t-${msg.type}">${icon} ${msg.type || ''}</span>` +
    (msg.ref ? `<span class="fm-ref">[${esc(msg.ref)}]</span>` : '') +
    `<span class="fm-body">${esc(trunc(msg.body || '', 130))}</span>`;

  feed.appendChild(el);

  // Cap feed length
  while (feed.children.length > 250) feed.removeChild(feed.firstChild);
}

function scrollFeed() {
  const feed = document.getElementById('channel-feed');
  if (feed) feed.scrollTop = feed.scrollHeight;
}

// Global action for clear button in HTML
window.clearFeed = function () {
  const feed = document.getElementById('channel-feed');
  if (feed) {
    feed.innerHTML = '<div class="feed-empty">Feed cleared.</div>';
  }
  allMessages = [];
};

// ── Summary ────────────────────────────────────────────────────────────────

function updateSummary() {
  const list = Object.values(rooms);
  const total    = list.length;
  const active   = list.filter(r => ['engineering','qa-review','fixing'].includes(r.status)).length;
  const passed   = list.filter(r => r.status === 'passed').length;
  const failed   = list.filter(r => r.status === 'failed-final').length;
  const pending  = list.filter(r => r.status === 'pending').length;
  const qa       = list.filter(r => r.status === 'qa-review').length;
  const eng      = list.filter(r => r.status === 'engineering').length;

  // Topbar pills
  setTxt('stat-active-text', `${active} active`);
  setTxt('stat-passed-text', `${passed} passed`);
  setTxt('stat-rooms-text', `${total} rooms`);

  // Summary chips
  setTxt('sum-pending', pending);
  setTxt('sum-eng', eng);
  setTxt('sum-qa', qa);
  setTxt('sum-passed', passed);
  setTxt('sum-failed', failed);

  if (currentView === 'matrix') renderGoalMatrix();

  // Pipeline highlight
  highlightPipeline(list);
}

function highlightPipeline(list) {
  const map = {
    'pipe-engineer': ['engineering','fixing'],
    'pipe-qa':       ['qa-review'],
    'pipe-release':  ['passed'],
    'pipe-manager':  ['pending'],
  };
  Object.entries(map).forEach(([id, statuses]) => {
    const el = document.getElementById(id);
    if (!el) return;
    const active = list.some(r => statuses.includes(r.status));
    el.classList.toggle('pipe-active', active);
  });
}

// ── Config ─────────────────────────────────────────────────────────────────

async function loadConfig() {
  try {
    const res  = await fetch('/api/config');
    const data = await res.json();
    const m = data.manager || {};
    setTxt('cfg-concurrent', m.max_concurrent_rooms ?? '—');
    setTxt('cfg-poll',       (m.poll_interval_seconds ?? '—') + 's');
    setTxt('cfg-retries',    m.max_engineer_retries ?? '—');
  } catch { /* offline */ }
}

// ── Manager Status ────────────────────────────────────────────────────────

async function pollManagerStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    setManagerRunning(data.running);
  } catch { /* server may be restarting */ }
}

function setManagerRunning(running) {
  const btn     = document.getElementById('launch-btn');
  const btnText = document.getElementById('launch-text');
  const btnIcon = document.getElementById('launch-icon');
  const stopBtn = document.getElementById('stop-btn');

  if (!btn) return;

  if (running) {
    btn.classList.add('running');
    if (btnIcon) btnIcon.textContent = '⟳';
    if (btnText) btnText.textContent = 'RUNNING…';
    if (stopBtn) stopBtn.style.display = 'block';
  } else {
    btn.classList.remove('running');
    btn.disabled = false;
    if (btnIcon) btnIcon.textContent = '▶';
    if (btnText) btnText.textContent = 'LAUNCH';
    if (stopBtn) stopBtn.style.display = 'none';
  }
}

window.stopRun = async function () {
  const stopBtn = document.getElementById('stop-btn');
  if (stopBtn) stopBtn.disabled = true;

  try {
    await fetch('/api/stop', { method: 'POST' });
    showLaunchStatus('Stopped.', '#ff9f43');
  } catch (err) {
    showLaunchStatus(`Stop failed: ${err.message}`, '#ff6b6b');
  }

  if (stopBtn) stopBtn.disabled = false;
  await pollManagerStatus();
};

// ── Plan Launcher ──────────────────────────────────────────────────────────

// Called by HTML onclick
window.launchPlan = async function () {
  const textarea = document.getElementById('plan-input');
  const btn      = document.getElementById('launch-btn');
  const btnText  = document.getElementById('launch-text');
  const btnIcon  = document.getElementById('launch-icon');
  const status   = document.getElementById('launch-status');

  if (!textarea) return;
  const plan = textarea.value.trim();
  if (!plan) { showLaunchStatus('Plan is empty.', '#ff6b6b'); return; }

  btn.disabled = true;
  if (btnIcon) btnIcon.textContent = '⟳';
  if (btnText) btnText.textContent = 'LAUNCHING…';
  showLaunchStatus('Submitting plan…', '#00d4ff');

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    showLaunchStatus(`✓ Launched — ${data.plan_file || 'ok'}`, '#00ff88');
    // Track launched plan and refresh history
    if (data.plan_id) {
      activePlanId = data.plan_id;
      // Load epics for the launched plan
      try {
        const planRes = await fetch(`/api/plans/${data.plan_id}`);
        const planData = await planRes.json();
        showEpicTracker(planData.epics || []);
      } catch { /* will populate on next poll */ }
    }
    loadPlanHistory();
    // Poll immediately so the button shows RUNNING state
    setTimeout(pollManagerStatus, 800);
  } catch (err) {
    showLaunchStatus(`✗ ${err.message}`, '#ff6b6b');
    btn.disabled = false;
    if (btnIcon) btnIcon.textContent = '▶';
    if (btnText) btnText.textContent = 'LAUNCH';
  }
};

function showLaunchStatus(msg, color) {
  const el = document.getElementById('launch-status');
  if (!el) return;
  el.textContent = msg;
  el.style.color = color;
  el.style.opacity = '1';
}

// Template loader (called by quick-action buttons)
window.loadTemplate = function (name) {
  const textarea = document.getElementById('plan-input');
  if (!textarea || !TEMPLATES[name]) return;
  textarea.value = TEMPLATES[name];
  textarea.focus();
};

// ── Plan History & Epic Tracker ─────────────────────────────────────────────

async function loadPlanHistory() {
  try {
    const res = await fetch('/api/plans');
    const data = await res.json();
    planHistory = data.plans || [];

    const select = document.getElementById('plan-select');
    const count = document.getElementById('plan-count');
    if (!select) return;

    // Keep the "new plan" option, add history
    select.innerHTML = '<option value="">— new plan —</option>';
    planHistory.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.plan_id;
      const date = p.created_at ? new Date(p.created_at).toLocaleDateString('en', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
      }) : '';
      opt.textContent = `${p.title || p.plan_id} (${p.epic_count} epics, ${date})`;
      opt.dataset.status = p.status;
      select.appendChild(opt);
    });

    if (count) count.textContent = `${planHistory.length} plans`;
    renderPlanQueue();
  } catch (e) {
    console.error('Failed to load plan history:', e);
  }
}

function renderPlanQueue() {
  const list = document.getElementById('plan-queue-list');
  if (!list) return;

  if (planHistory.length === 0) {
    list.innerHTML = '<div class="empty-queue">Queue is empty</div>';
    return;
  }

  list.innerHTML = planHistory.map(p => {
    let status = p.status;
    if (status === 'launched') status = 'active';
    else if (status === 'stored') status = 'queued';
    
    const statusClass = `status-${status}`;
    return `
      <div class="plan-queue-item ${status === 'active' ? 'active' : ''}" onclick="loadPlan('${esc(p.plan_id)}')">
        <div class="plan-queue-header">
          <span class="plan-queue-title">${esc(p.title || p.plan_id)}</span>
          <span class="plan-queue-status ${statusClass}">${status}</span>
        </div>
        <div style="font-size: 8px; color: var(--text-dim)">
          ${p.epic_count} epics • ${fmtTime(p.created_at)}
        </div>
      </div>
    `;
  }).join('');
}

window.loadPlan = async function (planId) {
  const select = document.getElementById('plan-select');
  const textarea = document.getElementById('plan-input');
  if (!textarea) return;

  if (select) select.value = planId;

  if (!planId) {
    activePlanId = null;
    hideEpicTracker();
    textarea.value = '';
    return;
  }

  try {
    const res = await fetch(`/api/plans/${planId}`);
    const data = await res.json();
    if (data.plan && data.plan.content) {
      textarea.value = data.plan.content;
      textarea.focus();
      activePlanId = planId;
      showEpicTracker(data.epics || []);
    }
  } catch (e) {
    console.error('Failed to load plan:', e);
  }
};

window.loadPlanFromHistory = async function () {
  const select = document.getElementById('plan-select');
  if (!select) return;
  loadPlan(select.value);
};

function showEpicTracker(epics) {
  const tracker = document.getElementById('epic-tracker');
  const list = document.getElementById('epic-list');
  if (!tracker || !list) return;

  if (!epics.length) {
    hideEpicTracker();
    return;
  }

  list.innerHTML = epics.map(e => {
    const statusClass = `st-${(e.status || 'pending').replace(' ', '-')}`;
    const label = (e.status || 'pending').toUpperCase();
    return `
      <div class="epic-item" onclick="selectRoom('${esc(e.room_id)}')">
        <span class="epic-ref">${esc(e.epic_ref)}</span>
        <span class="epic-title">${esc(trunc(e.title, 40))}</span>
        <span class="epic-status ${statusClass}">${label}</span>
      </div>
    `;
  }).join('');

  tracker.style.display = 'block';
}

function hideEpicTracker() {
  const tracker = document.getElementById('epic-tracker');
  if (tracker) tracker.style.display = 'none';
}

function updateEpicStatuses() {
  // Update epic statuses from current room state
  if (!activePlanId) return;
  const list = document.getElementById('epic-list');
  if (!list) return;

  const items = list.querySelectorAll('.epic-item');
  items.forEach(item => {
    const roomId = item.getAttribute('onclick')?.match(/'(room-\d+)'/)?.[1];
    if (!roomId || !rooms[roomId]) return;
    const room = rooms[roomId];
    const statusEl = item.querySelector('.epic-status');
    if (statusEl) {
      const statusClass = `st-${room.status.replace(' ', '-')}`;
      statusEl.className = `epic-status ${statusClass}`;
      statusEl.textContent = (room.status || 'pending').toUpperCase();
    }
  });
}

// ── Release Panel ──────────────────────────────────────────────────────────

function showRelease(content) {
  const bar    = document.getElementById('release-bar');
  const text   = document.getElementById('release-text');
  const toggle = document.getElementById('release-toggle');

  if (!bar) return;
  bar.style.display = 'block';
  bar.style.animation = 'releaseGlow 1s ease-out';

  if (text) text.textContent = content;

  // Auto-expand
  const contentEl = document.getElementById('release-content');
  if (contentEl) contentEl.style.display = 'block';
  if (toggle) toggle.textContent = '▴ collapse';
  releaseExpanded = true;

  celebrate();
}

window.toggleRelease = function () {
  const contentEl = document.getElementById('release-content');
  const toggle    = document.getElementById('release-toggle');
  if (!contentEl) return;
  releaseExpanded = !releaseExpanded;
  contentEl.style.display = releaseExpanded ? 'block' : 'none';
  if (toggle) toggle.textContent = releaseExpanded ? '▴ collapse' : '▾ expand';
};

function celebrate() {
  const items = ['🎉','✅','🚀','⬡','★','◆','✦'];
  for (let i = 0; i < 14; i++) {
    setTimeout(() => spawnParticle(items[i % items.length]), i * 90);
  }
}

function spawnParticle(emoji) {
  const el = document.createElement('span');
  Object.assign(el.style, {
    position: 'fixed',
    left: `${Math.random() * 100}vw`,
    top:  `${40 + Math.random() * 30}vh`,
    fontSize: `${14 + Math.random() * 20}px`,
    opacity: '1',
    pointerEvents: 'none',
    zIndex: '9999',
    transition: 'transform 1.6s ease-out, opacity 1.6s ease-out',
    userSelect: 'none',
  });
  el.textContent = emoji;
  document.body.appendChild(el);

  requestAnimationFrame(() => requestAnimationFrame(() => {
    el.style.transform = `translateY(-${120 + Math.random() * 200}px) rotate(${(Math.random()-0.5)*60}deg)`;
    el.style.opacity = '0';
  }));
  setTimeout(() => el.remove(), 2000);
}

// ── Connection Status ──────────────────────────────────────────────────────

function setConn(connected) {
  const dot   = document.getElementById('conn-dot');
  const label = document.getElementById('conn-status');

  if (dot) {
    dot.style.background  = connected ? '#00ff88' : '#ff6b6b';
    dot.style.boxShadow   = connected ? '0 0 8px #00ff8888' : 'none';
    dot.style.animation   = connected ? 'dotBlink 2s ease-in-out infinite' : 'none';
  }
  if (label) {
    label.textContent = connected ? 'LIVE' : 'RECONNECTING…';
    label.style.color = connected ? '#00ff8888' : '#ff6b6b88';
  }
}

// ── Initial Load ───────────────────────────────────────────────────────────

async function loadInitialState() {
  try {
    const [roomsRes, releaseRes] = await Promise.all([
      fetch('/api/rooms'),
      fetch('/api/release'),
    ]);

    const roomsData   = await roomsRes.json();
    const releaseData = await releaseRes.json();

    // Render rooms
    for (const room of (roomsData.rooms || [])) {
      rooms[room.room_id] = room;
      renderCard(room, false);
    }
    updateSummary();

    // Load channel history (sequential to preserve order)
    for (const room of (roomsData.rooms || [])) {
      try {
        const chRes  = await fetch(`/api/rooms/${room.room_id}/channel`);
        const chData = await chRes.json();
        (chData.messages || []).forEach(m => {
          allMessages.push({ roomId: room.room_id, msg: m });
          appendMsg(room.room_id, m, false);
        });
      } catch { /* skip room */ }
    }
    scrollFeed();

    if (releaseData.available && releaseData.content) {
      showRelease(releaseData.content);
    }

  } catch (err) {
    console.error('Initial load failed:', err);
  }
}

// ── Utilities ──────────────────────────────────────────────────────────────

function setTxt(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function trunc(s, n) {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

function fmtTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString('en', {
      hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return String(ts).slice(11, 19); }
}

function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Vector Search ───────────────────────────────────────────────────────────

let searchTimer = null;

function debouncedSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(doSearch, 300);
}

async function doSearch() {
  const input = document.getElementById('search-input');
  const resultsEl = document.getElementById('search-results');
  if (!input || !resultsEl) return;

  const q = input.value.trim();
  if (!q) {
    resultsEl.style.display = 'none';
    resultsEl.innerHTML = '';
    return;
  }

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
    if (!res.ok) {
      if (res.status === 503) {
        resultsEl.innerHTML = '<div class="search-result"><span style="color:var(--muted)">Vector search not available</span></div>';
        resultsEl.style.display = 'block';
      }
      return;
    }
    const data = await res.json();
    if (!data.results || data.results.length === 0) {
      resultsEl.innerHTML = '<div class="search-result"><span style="color:var(--muted)">No results</span></div>';
      resultsEl.style.display = 'block';
      return;
    }

    resultsEl.innerHTML = data.results.map(r => `
      <div class="search-result" onclick="filterRoom('${esc(r.room_id)}')">
        <div class="search-result-header">
          <span class="search-result-room">${esc(r.room_id)}</span>
          <span class="search-result-type">${esc(r.type)}</span>
          <span style="color:var(--muted)">${esc(r.ref)}</span>
          <span class="search-result-score">${(r.score * 100).toFixed(0)}%</span>
        </div>
        <div class="search-result-body">${esc(trunc(r.body, 120))}</div>
      </div>
    `).join('');
    resultsEl.style.display = 'block';
  } catch (err) {
    console.error('Search failed:', err);
  }
}

// Close search results on click outside
document.addEventListener('click', (e) => {
  const bar = document.getElementById('search-bar');
  const results = document.getElementById('search-results');
  if (bar && results && !bar.contains(e.target)) {
    results.style.display = 'none';
  }
});

// Filter room in channel feed when clicking a search result
function filterRoom(roomId) {
  const results = document.getElementById('search-results');
  if (results) results.style.display = 'none';
  // Use existing channel filter if available
  if (typeof channelFilter !== 'undefined') {
    channelFilter = roomId;
    renderFeed();
  }
}
