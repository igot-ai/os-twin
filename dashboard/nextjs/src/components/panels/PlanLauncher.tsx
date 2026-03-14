'use client';

import { useState, useCallback, useEffect } from 'react';
import { Plan, Epic, ManagerConfig, BrowseResult, DirEntry } from '@/types';
import { TEMPLATES } from '@/lib/constants';
import { apiGet, apiPost, apiFetch } from '@/lib/api';
import { trunc, fmtTime } from '@/lib/utils';

interface PlanLauncherProps {
  onPlanLaunched?: () => void;
}

export default function PlanLauncher({ onPlanLaunched }: PlanLauncherProps) {
  const [planText, setPlanText] = useState(TEMPLATES.hello);
  const [launchStatus, setLaunchStatus] = useState('');
  const [launchColor, setLaunchColor] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [config, setConfig] = useState<ManagerConfig>({});
  const [showNewProject, setShowNewProject] = useState(false);

  // Folder picker state
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [selectedPath, setSelectedPath] = useState('~');
  const [npTitle, setNpTitle] = useState('');
  const [npContent, setNpContent] = useState('');
  const [npStatus, setNpStatus] = useState('');

  // Load plans, config, and manager status
  useEffect(() => {
    loadPlanHistory();
    loadConfig();
    pollManagerStatus();
    const interval = setInterval(pollManagerStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadPlanHistory = useCallback(async () => {
    try {
      const data = await apiGet<{ plans: Plan[] }>('/api/plans');
      setPlans(data.plans || []);
    } catch (e) {
      console.error('Failed to load plan history:', e);
    }
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      const data = await apiGet<{ manager?: ManagerConfig }>('/api/config');
      setConfig(data.manager || {});
    } catch {
      // offline
    }
  }, []);

  const pollManagerStatus = useCallback(async () => {
    try {
      const data = await apiGet<{ running: boolean }>('/api/status');
      setIsRunning(data.running);
    } catch {
      // server may be restarting
    }
  }, []);

  const launchPlan = useCallback(async () => {
    if (!planText.trim()) {
      setLaunchStatus('Plan is empty.');
      setLaunchColor('#ff6b6b');
      return;
    }

    setLaunchStatus('Submitting plan…');
    setLaunchColor('#00d4ff');

    try {
      const res = await apiFetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: planText, plan_id: activePlanId }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setLaunchStatus(`✓ Launched — ${data.plan_file || 'ok'}`);
      setLaunchColor('#00ff88');

      if (data.plan_id) {
        setActivePlanId(data.plan_id);
        try {
          const planData = await apiGet<{ epics: Epic[] }>(`/api/plans/${data.plan_id}`);
          setEpics(planData.epics || []);
        } catch {
          // will populate on next poll
        }
      }

      loadPlanHistory();
      setTimeout(pollManagerStatus, 800);
      onPlanLaunched?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setLaunchStatus(`✗ ${msg}`);
      setLaunchColor('#ff6b6b');
    }
  }, [planText, loadPlanHistory, pollManagerStatus, onPlanLaunched]);

  const stopRun = useCallback(async () => {
    try {
      await apiPost('/api/stop');
      setLaunchStatus('Stopped.');
      setLaunchColor('#ff9f43');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setLaunchStatus(`Stop failed: ${msg}`);
      setLaunchColor('#ff6b6b');
    }
    pollManagerStatus();
  }, [pollManagerStatus]);

  const loadPlan = useCallback(async (planId: string) => {
    if (!planId) {
      setActivePlanId(null);
      setEpics([]);
      setPlanText('');
      return;
    }
    try {
      const data = await apiGet<{ plan: Plan; epics: Epic[] }>(`/api/plans/${planId}`);
      if (data.plan?.content) {
        setPlanText(data.plan.content);
        setActivePlanId(planId);
        setEpics(data.epics || []);
      }
    } catch (e) {
      console.error('Failed to load plan:', e);
    }
  }, []);

  const browseFolder = useCallback(async (path: string | null) => {
    try {
      const url = path ? `/api/fs/browse?path=${encodeURIComponent(path)}` : '/api/fs/browse';
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to browse');
      const data: BrowseResult = await res.json();
      setBrowseResult(data);
      setSelectedPath(data.current);
    } catch (err) {
      console.error('Browse error:', err);
    }
  }, []);

  const createNewProject = useCallback(async () => {
    if (!selectedPath || selectedPath === '~') {
      setNpStatus('Please select a project directory.');
      return;
    }
    setNpStatus('Creating project...');
    try {
      const body: Record<string, string> = { path: selectedPath, title: npTitle || 'Untitled' };
      if (npContent) body.content = npContent;

      const res = await apiFetch('/api/plans/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setNpStatus(`✓ Created: ${data.plan_id}`);
      setTimeout(() => { window.location.href = data.url; }, 500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setNpStatus(`✗ ${msg}`);
    }
  }, [selectedPath, npTitle, npContent]);

  return (
    <aside className="panel panel-left">
      <div className="panel-header">
        <span className="panel-title">▶ PLAN LAUNCHER</span>
        <button
          className="action-btn"
          style={{ fontSize: '0.75rem', padding: '4px 10px' }}
          onClick={() => {
            setShowNewProject((v) => !v);
            if (!showNewProject) browseFolder(null);
          }}
        >
          + New Project
        </button>
      </div>

      <div className="panel-body">
        {/* New Project Modal */}
        {showNewProject && (
          <div
            style={{
              background: 'var(--bg-secondary, #1e1e2e)',
              border: '1px solid var(--border-color, #333)',
              borderRadius: '8px',
              padding: '16px',
              marginBottom: '16px',
            }}
          >
            <label className="field-label">Project Directory</label>
            <div
              style={{
                border: '1px solid #333',
                borderRadius: '6px',
                background: '#1a1a2a',
                marginBottom: '10px',
                overflow: 'hidden',
              }}
            >
              {/* Breadcrumb */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '8px 10px',
                  borderBottom: '1px solid #333',
                  fontSize: '0.8rem',
                  fontFamily: "'JetBrains Mono',monospace",
                  color: '#aaa',
                  overflowX: 'auto',
                  whiteSpace: 'nowrap',
                }}
              >
                <span
                  style={{ cursor: 'pointer', color: '#7c5bf0' }}
                  onClick={() => browseFolder('/')}
                >
                  🏠
                </span>
                {browseResult &&
                  browseResult.current
                    .split('/')
                    .filter(Boolean)
                    .map((part, i, arr) => {
                      const accPath = '/' + arr.slice(0, i + 1).join('/');
                      const isLast = i === arr.length - 1;
                      return (
                        <span key={i}>
                          <span style={{ color: '#444', margin: '0 2px' }}>›</span>
                          {isLast ? (
                            <span style={{ color: '#e0e0e0', fontWeight: 500 }}>{part}</span>
                          ) : (
                            <span
                              style={{ cursor: 'pointer', color: '#7c5bf0' }}
                              onClick={() => browseFolder(accPath)}
                            >
                              {part}
                            </span>
                          )}
                        </span>
                      );
                    })}
              </div>

              {/* Directory listing */}
              <div style={{ maxHeight: '180px', overflowY: 'auto', padding: '4px 0' }}>
                {browseResult?.parent && (
                  <div
                    onClick={() => browseFolder(browseResult.parent!)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '6px 12px',
                      cursor: 'pointer',
                      fontFamily: "'JetBrains Mono',monospace",
                      fontSize: '0.8rem',
                      color: '#888',
                      borderBottom: '1px solid #1e1e2e',
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>📁</span>
                    <span>..</span>
                  </div>
                )}
                {browseResult?.dirs.length === 0 && (
                  <div
                    style={{
                      padding: '12px',
                      color: '#555',
                      textAlign: 'center',
                      fontSize: '0.8rem',
                    }}
                  >
                    No subdirectories
                  </div>
                )}
                {browseResult?.dirs.map((d: DirEntry) => (
                  <div
                    key={d.path}
                    onClick={() => browseFolder(d.path)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '6px 12px',
                      cursor: 'pointer',
                      fontFamily: "'JetBrains Mono',monospace",
                      fontSize: '0.8rem',
                      color: '#ccc',
                      borderBottom: '1px solid #1e1e2e',
                    }}
                  >
                    <span>📁</span>
                    <span style={{ flex: 1 }}>{d.name}</span>
                    {d.has_children && (
                      <span style={{ color: '#555', marginLeft: 'auto', fontSize: '0.7rem' }}>
                        ›
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Selected path */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 10px',
                  borderTop: '1px solid #333',
                  background: '#151525',
                }}
              >
                <span
                  style={{
                    color: '#666',
                    fontSize: '0.75rem',
                    fontFamily: "'JetBrains Mono',monospace",
                  }}
                >
                  Selected:
                </span>
                <span
                  style={{
                    color: '#7c5bf0',
                    fontSize: '0.8rem',
                    fontFamily: "'JetBrains Mono',monospace",
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {selectedPath}
                </span>
                <button
                  className="action-btn"
                  style={{
                    padding: '3px 10px',
                    fontSize: '0.7rem',
                    background: '#7c5bf0',
                    color: '#fff',
                    border: 'none',
                  }}
                  onClick={() => {
                    /* already selected via browseFolder */
                  }}
                >
                  ✓ Select
                </button>
              </div>
            </div>

            <label className="field-label">Project Name</label>
            <input
              type="text"
              placeholder="My New Project"
              value={npTitle}
              onChange={(e) => setNpTitle(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                marginBottom: '10px',
                borderRadius: '4px',
                border: '1px solid #333',
                background: '#2a2a2a',
                color: '#fff',
                fontFamily: "'JetBrains Mono',monospace",
                fontSize: '0.85rem',
              }}
            />
            <label className="field-label">Basic Plan (optional)</label>
            <textarea
              placeholder="Describe your project goals here..."
              value={npContent}
              onChange={(e) => setNpContent(e.target.value)}
              style={{
                width: '100%',
                height: '100px',
                padding: '8px',
                marginBottom: '10px',
                borderRadius: '4px',
                border: '1px solid #333',
                background: '#2a2a2a',
                color: '#fff',
                fontFamily: "'JetBrains Mono',monospace",
                fontSize: '0.85rem',
                resize: 'vertical' as const,
              }}
            />
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                className="action-btn"
                style={{ padding: '6px 14px' }}
                onClick={() => setShowNewProject(false)}
              >
                Cancel
              </button>
              <button
                className="launch-btn"
                style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                onClick={createNewProject}
              >
                Create &amp; Open
              </button>
            </div>
            {npStatus && (
              <div style={{ color: '#888', fontSize: '0.8rem', marginTop: '6px' }}>
                {npStatus}
              </div>
            )}
          </div>
        )}

        {/* Plan History */}
        <label className="field-label">Plan History</label>
        <div className="plan-history">
          <select
            className="plan-select"
            onChange={(e) => loadPlan(e.target.value)}
            value={activePlanId || ''}
          >
            <option value="">— new plan —</option>
            {plans.map((p) => {
              const date = p.created_at
                ? new Date(p.created_at).toLocaleDateString('en', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false,
                  })
                : '';
              return (
                <option key={p.plan_id} value={p.plan_id}>
                  {p.title || p.plan_id} ({p.epic_count} epics, {date})
                </option>
              );
            })}
          </select>
          <span className="plan-count">{plans.length} plans</span>
        </div>

        {/* Plan Queue */}
        <div className="plan-queue-section">
          <label className="field-label">Plan Queue</label>
          <div className="plan-queue-list">
            {plans.length === 0 ? (
              <div className="empty-queue">Queue is empty</div>
            ) : (
              plans.map((p) => {
                let status = p.status;
                if (status === 'launched') status = 'active';
                else if (status === 'stored') status = 'queued';
                const statusClass = `status-${status}`;
                return (
                  <div
                    key={p.plan_id}
                    className={`plan-queue-item${status === 'active' ? ' active' : ''}`}
                    onClick={() => loadPlan(p.plan_id)}
                  >
                    <div className="plan-queue-header">
                      <span className="plan-queue-title">{p.title || p.plan_id}</span>
                      <span className={`plan-queue-status ${statusClass}`}>{status}</span>
                    </div>
                    <div style={{ fontSize: '8px', color: 'var(--text-dim)' }}>
                      {p.epic_count} epics • {fmtTime(p.created_at)}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Plan Textarea */}
        <label className="field-label">Plan File</label>
        <textarea
          className="plan-textarea"
          value={planText}
          onChange={(e) => setPlanText(e.target.value)}
          placeholder={`# Plan: My Feature\n\n## Config\nworking_dir: .\n\n## Epic: EPIC-001 — Feature Title\n\nDescribe the feature to deliver...`}
          spellCheck={false}
        />

        {/* Launch Actions */}
        <div className="launch-actions">
          <button
            className={`launch-btn${isRunning ? ' running' : ''}`}
            onClick={launchPlan}
            disabled={isRunning}
          >
            <span className="btn-icon">{isRunning ? '⟳' : '▶'}</span>
            <span>{isRunning ? 'RUNNING…' : 'LAUNCH'}</span>
          </button>
          {isRunning && (
            <button className="stop-btn" onClick={stopRun}>
              ■ STOP
            </button>
          )}
        </div>

        {launchStatus && (
          <div className="launch-status" style={{ color: launchColor }}>
            {launchStatus}
          </div>
        )}

        {/* Quick Actions */}
        <div className="quick-actions">
          <label className="field-label">Quick Actions</label>
          <button className="action-btn" onClick={() => setPlanText(TEMPLATES.hello)}>
            hello world
          </button>
          <button className="action-btn" onClick={() => setPlanText(TEMPLATES.api)}>
            REST API
          </button>
          <button className="action-btn" onClick={() => setPlanText(TEMPLATES.fullstack)}>
            full-stack app
          </button>
        </div>

        {/* Epic Tracker */}
        {epics.length > 0 && (
          <div className="epic-tracker" style={{ display: 'block' }}>
            <label className="field-label">Epic Tracker</label>
            <div className="epic-list">
              {epics.map((e) => {
                const statusClass = `st-${(e.status || 'pending').replace(' ', '-')}`;
                return (
                  <div key={e.epic_ref} className="epic-item">
                    <span className="epic-ref">{e.epic_ref}</span>
                    <span className="epic-title">{trunc(e.title, 40)}</span>
                    <span className={`epic-status ${statusClass}`}>
                      {(e.status || 'pending').toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* System Config */}
        <div className="config-section">
          <label className="field-label">System Config</label>
          <div className="config-line">
            <span className="config-key">max_concurrent</span>
            <span className="config-val">{config.max_concurrent_rooms ?? '—'}</span>
          </div>
          <div className="config-line">
            <span className="config-key">poll_interval</span>
            <span className="config-val">
              {config.poll_interval_seconds != null
                ? `${config.poll_interval_seconds}s`
                : '—'}
            </span>
          </div>
          <div className="config-line">
            <span className="config-key">max_retries</span>
            <span className="config-val">{config.max_engineer_retries ?? '—'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
