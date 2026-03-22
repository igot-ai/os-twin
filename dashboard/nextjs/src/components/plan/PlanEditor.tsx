'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import MarkdownPreview from './MarkdownPreview';
import AIChatPanel from './AIChatPanel';
import { usePlanRefine } from '@/hooks/usePlanRefine';
import { usePlanVersions } from '@/hooks/usePlanVersions';

interface PlanEditorProps {
  planId: string;
  onClose: () => void;
  onPlanSaved?: () => void;
}

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
  resolved_skills?: any[];
}

export default function PlanEditor({ planId, onClose, onPlanSaved }: PlanEditorProps) {
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [activeTab, setActiveTab] = useState<'editor' | 'preview' | 'settings' | 'history' | 'skills'>('editor');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [roles, setRoles] = useState<RoleConfig[]>([]);
  const [roleConfig, setRoleConfig] = useState<Record<string, any>>({});
  const [isRefreshingRoles, setIsRefreshingRoles] = useState(false);

  const {
    chatHistory,
    isRefining,
    streamedResponse,
    error: aiError,
    refine,
    cancelRefine,
    clearHistory
  } = usePlanRefine();

  const {
    versions,
    selectedVersion,
    isLoading: isLoadingVersions,
    error: versionError,
    loadVersions,
    loadVersion,
    restoreVersion,
    clearSelection,
  } = usePlanVersions(planId);

  // Load plan
  useEffect(() => {
    if (!planId) return;
    apiGet<{ plan: any }>(`/api/plans/${planId}`).then(data => {
      if (data.plan) {
        setContent(data.plan.content || '');
        setTitle(data.plan.title || planId);
      }
    });

    // Load config
    apiGet<Record<string, any>>(`/api/plans/${planId}/config`).then(data => {
      setRoleConfig(data || {});
    });

    // Load roles metadata
    apiGet<{ roles: RoleConfig[] }>(`/api/plans/${planId}/roles`).then(data => {
      setRoles(data.roles || []);
    });
  }, [planId]);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus('Saving content...');
    try {
      await apiPost(`/api/plans/${planId}/save`, { content });

      if (Object.keys(roleConfig).length > 0) {
        setSaveStatus('Saving config...');
        await apiPost(`/api/plans/${planId}/config`, roleConfig);
      }

      setSaveStatus('Saved!');
      onPlanSaved?.();
      setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      setSaveStatus('Error saving');
    } finally {
      setIsSaving(false);
    }
  };

  const handleLaunch = async () => {
    await handleSave();
    try {
      await apiPost('/api/run', { plan: content, plan_id: planId });
      onClose(); // Close editor on launch
    } catch (err) {
      alert('Launch failed');
    }
  };

  const handleApplyAI = (newContent: string) => {
    setContent(newContent);
    setActiveTab('editor');
  };

  const handleRestore = async (version: number) => {
    const err = await restoreVersion(version);
    if (!err) {
      // Reload plan content after restore
      const data = await apiGet<{ plan: { content: string; title: string } }>(`/api/plans/${planId}`);
      if (data.plan) {
        setContent(data.plan.content || '');
        setTitle(data.plan.title || planId);
      }
      onPlanSaved?.();
    }
  };

  const updateRoleModel = (roleName: string, model: string) => {
    setRoleConfig(prev => ({
      ...prev,
      [roleName]: {
        ...prev[roleName],
        default_model: model
      }
    }));
  };

  return (
    <div className="plan-editor-overlay">
      <div className="plan-editor-container glass">
        {/* Header */}
        <header className="plan-editor-header">
          <div className="editor-logo-area">
            <span className="editor-hex">⬡</span>
            <div className="editor-title-group">
              <span className="editor-id">{planId}</span>
              <h1 className="editor-title">{title}</h1>
            </div>
          </div>
          <div className="editor-actions">
            {saveStatus && <span className="save-status-msg">{saveStatus}</span>}
            <button className="editor-btn editor-btn-save" onClick={handleSave} disabled={isSaving}>
              {isSaving ? '...' : 'Save'}
            </button>
            <button className="editor-btn editor-btn-launch" onClick={handleLaunch}>
              Launch
            </button>
            <button className="editor-btn editor-btn-close" onClick={onClose}>
              ✕
            </button>
          </div>
        </header>

        {/* Main Area */}
        <div className="editor-main">
          {/* Left Column: Editor/Preview/Settings */}
          <div className="editor-view-column">
            <div className="editor-tabs">
              <button
                className={`editor-tab ${activeTab === 'editor' ? 'active' : ''}`}
                onClick={() => setActiveTab('editor')}
              >
                Editor
              </button>
              <button
                className={`editor-tab ${activeTab === 'preview' ? 'active' : ''}`}
                onClick={() => setActiveTab('preview')}
              >
                Preview
              </button>
              <button
                className={`editor-tab ${activeTab === 'settings' ? 'active' : ''}`}
                onClick={() => setActiveTab('settings')}
              >
                Roles Settings
              </button>
              <button
                className={`editor-tab ${activeTab === 'skills' ? 'active' : ''}`}
                onClick={() => setActiveTab('skills')}
              >
                Resolved Skills
              </button>
              <button
                className={`editor-tab ${activeTab === 'history' ? 'active' : ''}`}
                onClick={() => { setActiveTab('history'); loadVersions(); }}
              >
                History{versions.length > 0 ? ` (${versions.length})` : ''}
              </button>
            </div>

            <div className="editor-content-area">
              {activeTab === 'editor' && (
                <textarea
                  className="editor-textarea"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="# Plan: ..."
                  spellCheck={false}
                />
              )}
              {activeTab === 'preview' && (
                <MarkdownPreview content={content} />
              )}
              {activeTab === 'settings' && (
                <div className="editor-settings-view">
                  <h2 className="settings-title">Role Overrides</h2>
                  <p className="settings-desc">Customize models for this plan. These take precedence over global settings.</p>

                  <div className="roles-grid">
                    {roles.length === 0 ? <p className="muted-text">Loading roles...</p> : roles.map(role => (
                      <div key={role.name} className="role-card glass">
                        <div className="role-card-header">
                          <span className="role-name">{role.name}</span>
                        </div>
                        <p className="role-desc">{role.description}</p>
                        <div className="role-field">
                          <label>Model</label>
                          <select
                            value={roleConfig[role.name]?.default_model || role.default_model}
                            onChange={(e) => updateRoleModel(role.name, e.target.value)}
                          >
                            <option value="gemini-3-flash-preview">Gemini 3 Flash</option>
                            <option value="gemini-3.1-pro-preview">Gemini 3.1 Pro</option>
                            <option value="anthropic:claude-opus-4-6">Claude 4.6 Opus</option>
                            <option value="anthropic:claude-sonnet-4-6">Claude 4.6 Sonnet</option>
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {activeTab === 'skills' && (
                <div className="editor-settings-view">
                  <h2 className="settings-title">Resolved Skills for This Plan</h2>
                  <p className="settings-desc">These are the skills that will be assigned to each role during execution.</p>

                  <div className="roles-grid">
                    {roles.length === 0 ? <p className="muted-text">Loading roles...</p> : roles.map(role => (
                      <div key={role.name} className="role-card glass" style={{ borderLeft: '3px solid var(--purple)' }}>
                        <div className="role-card-header">
                          <span className="role-name">{role.name}</span>
                          <span style={{ fontSize: '10px', color: 'var(--purple)', background: 'rgba(192, 132, 252, 0.1)', padding: '1px 6px', borderRadius: '4px' }}>
                            {role.resolved_skills?.length || 0} skills
                          </span>
                        </div>
                        <div className="role-skills-list" style={{ marginTop: '10px' }}>
                          {role.resolved_skills && role.resolved_skills.length > 0 ? (
                            role.resolved_skills.map((s: any) => (
                              <div key={s.name} className="role-skill-item" style={{ fontSize: '11px', padding: '4px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span>{s.name}</span>
                                <span style={{ fontSize: '9px', opacity: 0.6 }}>{s.trust_level}</span>
                              </div>
                            ))
                          ) : (
                            <p className="muted-text" style={{ fontSize: '10px' }}>No skills resolved.</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {activeTab === 'history' && (
                <div className="editor-settings-view">
                  <h2 className="settings-title">Version History</h2>
                  <p className="settings-desc">Previous versions of this plan. Click to view, restore to revert.</p>

                  {isLoadingVersions && <p className="muted-text">Loading versions...</p>}
                  {versionError && <p style={{ color: '#ff6b6b', fontSize: '0.85rem' }}>{versionError}</p>}

                  {selectedVersion ? (
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                        <button
                          className="editor-btn editor-btn-save"
                          style={{ fontSize: '0.8rem', padding: '4px 12px' }}
                          onClick={clearSelection}
                        >← Back</button>
                        <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: '0.85rem', color: '#aaa' }}>
                          v{selectedVersion.version} · {selectedVersion.change_source} · {new Date(selectedVersion.created_at).toLocaleString()}
                        </span>
                        <button
                          className="editor-btn editor-btn-launch"
                          style={{ fontSize: '0.8rem', padding: '4px 12px', marginLeft: 'auto' }}
                          onClick={() => handleRestore(selectedVersion.version)}
                        >Restore This Version</button>
                      </div>
                      <pre style={{
                        background: '#1a1a2a',
                        border: '1px solid #333',
                        borderRadius: '6px',
                        padding: '14px',
                        fontSize: '0.8rem',
                        fontFamily: "'JetBrains Mono',monospace",
                        color: '#ccc',
                        overflow: 'auto',
                        maxHeight: 'calc(100vh - 360px)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}>
                        {selectedVersion.content || '(no content)'}
                      </pre>
                    </div>
                  ) : (
                    <div className="version-list" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {versions.length === 0 && !isLoadingVersions && (
                        <p className="muted-text">No versions yet. Versions are created when you save changes.</p>
                      )}
                      {versions.map((v) => {
                        const sourceColors: Record<string, string> = {
                          manual_save: '#7c5bf0',
                          ai_refine: '#00d4ff',
                          expansion: '#00ff88',
                          before_restore: '#ff9f43',
                        };
                        return (
                          <div
                            key={v.id}
                            onClick={() => loadVersion(v.version)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '12px',
                              padding: '10px 14px',
                              background: '#1a1a2a',
                              border: '1px solid #2a2a3a',
                              borderRadius: '6px',
                              cursor: 'pointer',
                              transition: 'border-color 0.2s, background 0.2s',
                            }}
                            onMouseEnter={(e) => {
                              (e.currentTarget as HTMLDivElement).style.borderColor = '#7c5bf0';
                              (e.currentTarget as HTMLDivElement).style.background = '#1e1e30';
                            }}
                            onMouseLeave={(e) => {
                              (e.currentTarget as HTMLDivElement).style.borderColor = '#2a2a3a';
                              (e.currentTarget as HTMLDivElement).style.background = '#1a1a2a';
                            }}
                          >
                            <span style={{
                              fontFamily: "'JetBrains Mono',monospace",
                              fontSize: '0.85rem',
                              fontWeight: 600,
                              color: '#e0e0e0',
                              minWidth: '32px',
                            }}>v{v.version}</span>
                            <span style={{
                              flex: 1,
                              fontSize: '0.8rem',
                              color: '#999',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}>{v.title}</span>
                            <span style={{
                              fontSize: '0.7rem',
                              padding: '2px 8px',
                              borderRadius: '10px',
                              background: (sourceColors[v.change_source] || '#555') + '22',
                              color: sourceColors[v.change_source] || '#888',
                              border: `1px solid ${sourceColors[v.change_source] || '#555'}44`,
                              fontFamily: "'JetBrains Mono',monospace",
                              whiteSpace: 'nowrap',
                            }}>{v.change_source.replace('_', ' ')}</span>
                            <span style={{
                              fontSize: '0.75rem',
                              color: '#666',
                              fontFamily: "'JetBrains Mono',monospace",
                              whiteSpace: 'nowrap',
                            }}>{new Date(v.created_at).toLocaleString()}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: AI Assistant */}
          <aside className="editor-ai-column">
            <AIChatPanel
              chatHistory={chatHistory}
              isRefining={isRefining}
              streamedResponse={streamedResponse}
              error={aiError}
              onSendMessage={(msg) => refine(msg, content, planId)}
              onApplyToEditor={handleApplyAI}
              onCancel={cancelRefine}
              onClearHistory={clearHistory}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
