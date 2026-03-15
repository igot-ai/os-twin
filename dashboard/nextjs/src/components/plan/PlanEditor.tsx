'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import MarkdownPreview from './MarkdownPreview';
import AIChatPanel from './AIChatPanel';
import { usePlanRefine } from '@/hooks/usePlanRefine';

interface PlanEditorProps {
  planId: string;
  onClose: () => void;
  onPlanSaved?: () => void;
}

interface RoleConfig {
  name: string;
  default_model: string;
  description: string;
}

export default function PlanEditor({ planId, onClose, onPlanSaved }: PlanEditorProps) {
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [activeTab, setActiveTab] = useState<'editor' | 'preview' | 'settings'>('editor');
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
                            <option value="gpt-4o">GPT-4o</option>
                            <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
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
