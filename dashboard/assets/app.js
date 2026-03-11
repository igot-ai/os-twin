/**
 * Agent OS Command Center — Real-time SSE Client
 * TASK-003 + TASK-004: SSE client, DOM wiring, animations, integration
 */

'use strict';

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_COLOR = {
  pending:        '#555',
  engineering:    '#00d4ff',
  'qa-review':    '#ffd93d',
  fixing:         '#ff9f43',
  passed:         '#00ff88',
  'failed-final': '#ff6b6b',
};

const STATUS_LABEL = {
  pending:        'PENDING',
  engineering:    'ENGINEERING',
  'qa-review':    'QA REVIEW',
  fixing:         'FIXING',
  passed:         'PASSED',
  'failed-final': 'FAILED',
};

const MSG_ICON = {
  task: '📋', done: '✓', review: '🔍', pass: '✅',
  fail: '✗', fix: '🔧', signoff: '✍', release: '🚀', error: '⚠',
};

const PROGRESS_PCT = {
  pending: 5, engineering: 35, 'qa-review': 65,
  fixing: 45, passed: 100, 'failed-final': 100,
};

const TEMPLATES = {
  hello: `# Plan: Hello World

## Config
working_dir: .

## Task: TASK-001 — Create hello module

Build hello.py with a greet() function.

Acceptance criteria:
- greet("World") returns "Hello, World!"
- Module is importable

## Task: TASK-002 — Add pytest tests

Write test_hello.py covering the greet() function.

Acceptance criteria:
- pytest passes with 3+ assertions
`,

  api: `# Plan: REST API

## Config
working_dir: .

## Task: TASK-001 — FastAPI skeleton

Create main.py with FastAPI app, health endpoint.

Acceptance criteria:
- GET /health returns {"status":"ok"}

## Task: TASK-002 — Data models + CRUD

Add Pydantic models and CRUD endpoints.

Acceptance criteria:
- POST /items creates item
- GET /items lists all items

## Task: TASK-003 — Tests

Write pytest tests for all endpoints.

Acceptance criteria:
- All endpoints tested
- 90%+ coverage
`,

  fullstack: `# Plan: Full-Stack App

## Config
working_dir: .

## Task: TASK-001 — Backend API

FastAPI backend with SQLite, auth, CRUD.

## Task: TASK-002 — Frontend SPA

React SPA with login, data views.

## Task: TASK-003 — Docker compose

Containerize frontend + backend.

## Task: TASK-004 — CI pipeline

GitHub Actions: lint, test, build, push.
`,
};

// ── State ──────────────────────────────────────────────────────────────────

let rooms = {};
let allMessages = [];
let channelFilter = null;
let eventSource = null;
let reconnectMs = 1000;
let releaseExpanded = false;

// ── Boot ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadConfig();
  loadInitialState().then(() => connect());
  pollManagerStatus();
  setInterval(pollManagerStatus, 3000);
});

// ── SSE ────────────────────────────────────────────────────────────────────

function connect() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource('/api/events');

  eventSource.onopen = () => {
    reconnectMs = 1000;
    setConn(true);
  };

  eventSource.onmessage = (e) => {
    try { dispatch(JSON.parse(e.data)); }
    catch (err) { console.error('SSE parse error', err); }
  };

  eventSource.onerror = () => {
    setConn(false);
    eventSource.close();
    eventSource = null;
    setTimeout(connect, reconnectMs);
    reconnectMs = Math.min(reconnectMs * 2, 30000);
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
      updateSummary();
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
  }
}

// ── War-Room Cards ─────────────────────────────────────────────────────────

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
    <div class="rc-bar-wrap">
      <div class="rc-bar" style="width:${pct}%;background:${color}${isActive ? ';animation:barPulse 1.5s ease-in-out infinite' : ''}"></div>
    </div>
    <div class="rc-foot">
      <span style="color:#555">⬡ ${room.message_count}</span>
      ${room.retries > 0 ? `<span style="color:#ff9f43">↻${room.retries}</span>` : ''}
      <span style="color:#333">${fmtTime(room.last_activity)}</span>
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
  const title = document.querySelector('.panel-right .panel-title');
  if (title) title.textContent = channelFilter ? `▸ ${channelFilter}` : '▸ CHANNEL FEED';
  reloadFeed();
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
